"""LLM Provider Abstraction Layer.

Supports multiple backends:
- deterministic: Fixed template outputs for testing
- local: Local model inference (Qwen2.5-0.5B-Instruct via transformers)
- openai: OpenAI API (requires OPENAI_API_KEY)
- anthropic: Anthropic API (requires ANTHROPIC_API_KEY)

Reference: Chapter 7 (P113-131) - Multi-Agent model invocation
"""

from __future__ import annotations

import hashlib
import json
import os
import time
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Literal

from pydantic import BaseModel


class ProviderType(str, Enum):
    """LLM provider types."""
    DETERMINISTIC = "deterministic"
    LOCAL = "local"
    OPENAI = "openai"
    ANTHROPIC = "anthropic"


@dataclass
class LLMCallTrace:
    """Trace of a single LLM call for auditing."""
    call_id: str
    timestamp: str
    provider: str
    model_id: str
    model_revision: str = ""
    model_license: str = ""
    
    role: str = ""
    stage: str = ""
    
    prompt: str = ""
    prompt_hash: str = ""
    prompt_tokens: int = 0
    
    response: str = ""
    response_hash: str = ""
    response_tokens: int = 0
    
    latency_ms: int = 0
    status: Literal["success", "error", "timeout", "fallback"] = "success"
    error_message: str = ""
    finish_reason: str = "unknown"  # stop, length, error
    
    # Parsed output if applicable
    parsed_output: dict[str, Any] = field(default_factory=dict)
    parse_success: bool = True
    validation_status: str = ""  # VALID, TRUNCATED, PARSE_FAILED, etc.
    validation_issues: list[str] = field(default_factory=list)
    
    def to_dict(self) -> dict[str, Any]:
        return {
            "call_id": self.call_id,
            "timestamp": self.timestamp,
            "provider": self.provider,
            "model_id": self.model_id,
            "model_revision": self.model_revision,
            "model_license": self.model_license,
            "role": self.role,
            "stage": self.stage,
            "prompt": self.prompt,
            "prompt_hash": self.prompt_hash,
            "prompt_tokens": self.prompt_tokens,
            "response": self.response,
            "response_hash": self.response_hash,
            "response_tokens": self.response_tokens,
            "latency_ms": self.latency_ms,
            "status": self.status,
            "error_message": self.error_message,
            "finish_reason": self.finish_reason,
            "parsed_output": self.parsed_output,
            "parse_success": self.parse_success,
            "validation_status": self.validation_status,
            "validation_issues": self.validation_issues,
        }


class LLMProvider(ABC):
    """Abstract base class for LLM providers."""
    
    @property
    @abstractmethod
    def provider_type(self) -> ProviderType:
        """Return provider type."""
        pass
    
    @property
    @abstractmethod
    def model_id(self) -> str:
        """Return model identifier."""
        pass
    
    @property
    def model_revision(self) -> str:
        """Return model revision/version."""
        return ""
    
    @property
    def model_license(self) -> str:
        """Return model license."""
        return ""
    
    @abstractmethod
    def generate(
        self,
        messages: list[dict[str, str]],
        max_tokens: int = 256,
        temperature: float = 0.7,
        role: str = "",
        stage: str = "",
    ) -> LLMCallTrace:
        """Generate response from messages."""
        pass
    
    def _generate_call_id(self) -> str:
        """Generate unique call ID."""
        return f"CALL-{datetime.now().strftime('%Y%m%d%H%M%S%f')[:17]}"
    
    def _hash_text(self, text: str) -> str:
        """Generate hash of text."""
        return hashlib.sha256(text.encode()).hexdigest()[:16]


class DeterministicProvider(LLMProvider):
    """Deterministic provider - returns fixed templates.
    
    For testing workflow logic without actual LLM calls.
    """
    
    def __init__(self, templates: dict[str, str] | None = None):
        self._templates = templates or {}
    
    @property
    def provider_type(self) -> ProviderType:
        return ProviderType.DETERMINISTIC
    
    @property
    def model_id(self) -> str:
        return "deterministic-template-v1"
    
    def generate(
        self,
        messages: list[dict[str, str]],
        max_tokens: int = 256,
        temperature: float = 0.7,
        role: str = "",
        stage: str = "",
    ) -> LLMCallTrace:
        call_id = self._generate_call_id()
        timestamp = datetime.now().isoformat()
        
        prompt = json.dumps(messages, ensure_ascii=False)
        
        # Use template if available, otherwise generate default
        template_key = f"{role}_{stage}"
        if template_key in self._templates:
            response = self._templates[template_key]
        else:
            response = f"[DETERMINISTIC] {role} output for {stage}"
        
        return LLMCallTrace(
            call_id=call_id,
            timestamp=timestamp,
            provider=self.provider_type.value,
            model_id=self.model_id,
            role=role,
            stage=stage,
            prompt=prompt,
            prompt_hash=self._hash_text(prompt),
            prompt_tokens=len(prompt.split()),
            response=response,
            response_hash=self._hash_text(response),
            response_tokens=len(response.split()),
            latency_ms=0,
            status="success",
        )


class LocalModelProvider(LLMProvider):
    """Local model provider using HuggingFace transformers.
    
    Supports Qwen2.5 instruction models (0.5B, 1.5B, 3B).
    Default: 1.5B for better quality while staying on CPU.
    
    License: Apache 2.0
    """
    
    # Model configurations
    MODELS = {
        "0.5B": {
            "model_id": "Qwen/Qwen2.5-0.5B-Instruct",
            "revision": "7ae557604adf67be50417f59c2c2f167def9a775",
        },
        "1.5B": {
            "model_id": "Qwen/Qwen2.5-1.5B-Instruct",
            "revision": "main",
        },
        "3B": {
            "model_id": "Qwen/Qwen2.5-3B-Instruct",
            "revision": "main",
        },
    }
    
    MODEL_LICENSE = "Apache-2.0"
    CACHE_DIR = "/tmp/hf_models"
    
    def __init__(self, model_size: str = "1.5B"):
        """Initialize with specified model size."""
        if model_size not in self.MODELS:
            raise ValueError(f"Unknown model size: {model_size}. Available: {list(self.MODELS.keys())}")
        
        self._model_size = model_size
        self._model_config = self.MODELS[model_size]
        self._model = None
        self._tokenizer = None
        self._loaded = False
    
    @property
    def provider_type(self) -> ProviderType:
        return ProviderType.LOCAL
    
    @property
    def model_id(self) -> str:
        return self._model_config["model_id"]
    
    @property
    def model_revision(self) -> str:
        return self._model_config["revision"]
    
    @property
    def model_license(self) -> str:
        return self.MODEL_LICENSE
    
    @property
    def model_size(self) -> str:
        return self._model_size
    
    def _load_model(self):
        """Lazy load model on first use."""
        if self._loaded:
            return
        
        import torch
        from transformers import AutoModelForCausalLM, AutoTokenizer
        
        print(f"    加载模型: {self.model_id} ({self._model_size})...")
        
        self._tokenizer = AutoTokenizer.from_pretrained(
            self.model_id,
            cache_dir=self.CACHE_DIR,
        )
        
        self._model = AutoModelForCausalLM.from_pretrained(
            self.model_id,
            cache_dir=self.CACHE_DIR,
            torch_dtype=torch.float32,
            device_map="cpu",
            low_cpu_mem_usage=True,
        )
        
        self._loaded = True
        print(f"    模型加载完成: {self.model_id}")
    
    def generate(
        self,
        messages: list[dict[str, str]],
        max_tokens: int = 256,
        temperature: float = 0.7,
        role: str = "",
        stage: str = "",
    ) -> LLMCallTrace:
        import torch
        
        call_id = self._generate_call_id()
        timestamp = datetime.now().isoformat()
        prompt = json.dumps(messages, ensure_ascii=False)
        
        try:
            self._load_model()
            
            # Apply chat template
            text = self._tokenizer.apply_chat_template(
                messages,
                tokenize=False,
                add_generation_prompt=True,
            )
            
            inputs = self._tokenizer([text], return_tensors="pt")
            input_tokens = inputs["input_ids"].shape[1]
            
            start_time = time.time()
            
            with torch.no_grad():
                outputs = self._model.generate(
                    **inputs,
                    max_new_tokens=max_tokens,
                    temperature=temperature if temperature > 0 else 0.01,
                    do_sample=True,
                    pad_token_id=self._tokenizer.eos_token_id,
                    return_dict_in_generate=True,
                    output_scores=False,
                )
            
            end_time = time.time()
            latency_ms = int((end_time - start_time) * 1000)
            
            # Extract response
            generated_ids = outputs.sequences[0][inputs["input_ids"].shape[1]:]
            response = self._tokenizer.decode(generated_ids, skip_special_tokens=True)
            output_tokens = len(generated_ids)
            
            # Determine finish reason
            finish_reason = "stop"
            if output_tokens >= max_tokens:
                finish_reason = "length"
            
            return LLMCallTrace(
                call_id=call_id,
                timestamp=timestamp,
                provider=self.provider_type.value,
                model_id=self.model_id,
                model_revision=self.model_revision,
                model_license=self.model_license,
                role=role,
                stage=stage,
                prompt=prompt,
                prompt_hash=self._hash_text(prompt),
                prompt_tokens=input_tokens,
                response=response,
                response_hash=self._hash_text(response),
                response_tokens=output_tokens,
                latency_ms=latency_ms,
                status="success",
                finish_reason=finish_reason,
            )
            
        except Exception as e:
            return LLMCallTrace(
                call_id=call_id,
                timestamp=timestamp,
                provider=self.provider_type.value,
                model_id=self.model_id,
                role=role,
                stage=stage,
                prompt=prompt,
                prompt_hash=self._hash_text(prompt),
                status="error",
                error_message=str(e),
            )


class LLMProviderFactory:
    """Factory for creating LLM providers."""
    
    _local_providers: dict[str, LocalModelProvider] = {}
    
    @classmethod
    def create(
        cls,
        provider_type: ProviderType | str,
        model_size: str = "1.5B",
    ) -> LLMProvider:
        """Create provider by type and model size."""
        if isinstance(provider_type, str):
            provider_type = ProviderType(provider_type)
        
        if provider_type == ProviderType.DETERMINISTIC:
            return DeterministicProvider()
        
        elif provider_type == ProviderType.LOCAL:
            # Reuse provider by model size
            if model_size not in cls._local_providers:
                cls._local_providers[model_size] = LocalModelProvider(model_size)
            return cls._local_providers[model_size]
        
        elif provider_type == ProviderType.OPENAI:
            api_key = os.getenv("OPENAI_API_KEY")
            if not api_key:
                raise ValueError("OPENAI_API_KEY not set")
            raise NotImplementedError("OpenAI provider not implemented - use local instead")
        
        elif provider_type == ProviderType.ANTHROPIC:
            api_key = os.getenv("ANTHROPIC_API_KEY")
            if not api_key:
                raise ValueError("ANTHROPIC_API_KEY not set")
            raise NotImplementedError("Anthropic provider not implemented - use local instead")
        
        else:
            raise ValueError(f"Unknown provider type: {provider_type}")
    
    @classmethod
    def create_local(cls, model_size: str = "1.5B") -> LocalModelProvider:
        """Create local provider with specific model size."""
        return cls.create(ProviderType.LOCAL, model_size)
    
    @classmethod
    def get_available_providers(cls) -> list[ProviderType]:
        """Get list of available providers."""
        available = [ProviderType.DETERMINISTIC]
        
        # Check if transformers is available for local
        try:
            import transformers
            available.append(ProviderType.LOCAL)
        except ImportError:
            pass
        
        # Check API keys
        if os.getenv("OPENAI_API_KEY"):
            available.append(ProviderType.OPENAI)
        if os.getenv("ANTHROPIC_API_KEY"):
            available.append(ProviderType.ANTHROPIC)
        
        return available
    
    @classmethod
    def get_available_model_sizes(cls) -> list[str]:
        """Get available local model sizes."""
        return list(LocalModelProvider.MODELS.keys())


class LLMCallRegistry:
    """Registry for tracking all LLM calls in a run."""
    
    def __init__(self):
        self._calls: list[LLMCallTrace] = []
    
    def record(self, trace: LLMCallTrace):
        """Record a call trace."""
        self._calls.append(trace)
    
    def get_all(self) -> list[LLMCallTrace]:
        """Get all recorded calls."""
        return self._calls.copy()
    
    def get_summary(self) -> dict[str, Any]:
        """Get summary of all calls."""
        if not self._calls:
            return {
                "total_calls": 0,
                "successful_calls": 0,
                "failed_calls": 0,
                "total_latency_ms": 0,
                "providers_used": [],
            }
        
        successful = [c for c in self._calls if c.status == "success"]
        failed = [c for c in self._calls if c.status != "success"]
        providers = list(set(c.provider for c in self._calls))
        
        return {
            "total_calls": len(self._calls),
            "successful_calls": len(successful),
            "failed_calls": len(failed),
            "total_prompt_tokens": sum(c.prompt_tokens for c in self._calls),
            "total_response_tokens": sum(c.response_tokens for c in self._calls),
            "total_latency_ms": sum(c.latency_ms for c in self._calls),
            "avg_latency_ms": sum(c.latency_ms for c in self._calls) // len(self._calls),
            "providers_used": providers,
            "models_used": list(set(c.model_id for c in self._calls)),
        }
    
    def to_json(self) -> str:
        """Export all calls to JSON."""
        return json.dumps(
            [c.to_dict() for c in self._calls],
            ensure_ascii=False,
            indent=2,
        )
    
    def save(self, path: str):
        """Save all calls to file."""
        with open(path, "w", encoding="utf-8") as f:
            f.write(self.to_json())
