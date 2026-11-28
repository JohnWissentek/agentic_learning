"""Model Manifest and Reproducibility Documentation.

This module provides complete reproducibility information for the local LLM model
used in the multi-agent workflow.

Reference: HuggingFace Model Hub
"""

from __future__ import annotations
from typing import Any
import hashlib

# Model identification - exact reproducibility info
MODEL_MANIFEST = {
    "model_id": "Qwen/Qwen2.5-0.5B-Instruct",
    "model_revision": "7ae557604adf67be50417f59c2c2f167def9a775",
    "model_license": "Apache-2.0",
    "huggingface_url": "https://huggingface.co/Qwen/Qwen2.5-0.5B-Instruct",
    "model_card_url": "https://huggingface.co/Qwen/Qwen2.5-0.5B-Instruct/blob/main/README.md",
    "parameters": "0.5B",
    "context_length": 32768,
    "languages": ["en", "zh"],
    "base_model": "Qwen/Qwen2.5-0.5B",
    "model_type": "causal-lm",
    "architecture": "Qwen2ForCausalLM",
    "tokenizer": "Qwen2Tokenizer",
    "dtype_inference": "float32",
    "device": "cpu",
    "framework": "transformers",
    "framework_version_min": "4.37.0",
    
    "weight_files": [
        "model.safetensors",
        "config.json",
        "tokenizer.json",
        "tokenizer_config.json",
        "vocab.json",
        "merges.txt",
        "generation_config.json",
    ],
    
    "download_script": '''#!/bin/bash
# Download Qwen2.5-0.5B-Instruct weights for reproducibility
# Requires: pip install huggingface_hub

from huggingface_hub import snapshot_download

snapshot_download(
    repo_id="Qwen/Qwen2.5-0.5B-Instruct",
    revision="7ae557604adf67be50417f59c2c2f167def9a775",
    local_dir="./qwen2.5-0.5b-instruct",
    local_dir_use_symlinks=False,
)
''',
    
    "python_download_script": '''
from huggingface_hub import snapshot_download

model_path = snapshot_download(
    repo_id="Qwen/Qwen2.5-0.5B-Instruct",
    revision="7ae557604adf67be50417f59c2c2f167def9a775",
)
print(f"Model downloaded to: {model_path}")
''',
    
    "inference_code": '''
from transformers import AutoModelForCausalLM, AutoTokenizer

model_id = "Qwen/Qwen2.5-0.5B-Instruct"
revision = "7ae557604adf67be50417f59c2c2f167def9a775"

tokenizer = AutoTokenizer.from_pretrained(model_id, revision=revision)
model = AutoModelForCausalLM.from_pretrained(
    model_id,
    revision=revision,
    torch_dtype="auto",
    device_map="auto",
)

messages = [
    {"role": "system", "content": "You are a helpful assistant."},
    {"role": "user", "content": "Hello!"},
]

text = tokenizer.apply_chat_template(messages, tokenize=False, add_generation_prompt=True)
inputs = tokenizer([text], return_tensors="pt").to(model.device)
outputs = model.generate(**inputs, max_new_tokens=256)
response = tokenizer.decode(outputs[0], skip_special_tokens=True)
''',
    
    "limitations": [
        "0.5B参数量有限，复杂推理能力受限",
        "生成可能截断、重复或格式不完整",
        "JSON解析可能失败，需要fallback处理",
        "不适合替代专业工程验证",
        "输出需要人工审查，不可直接用于决策",
    ],
    
    "quality_markers": {
        "parse_success": "JSON成功解析",
        "truncated": "输出被截断",
        "invalid_format": "格式无效",
        "needs_review": "需要人工审查",
        "model_limitation": "模型能力限制",
    },
}


# v0.3.1 Research Data Integration - FINAL AUTHORITATIVE VERSION
V031_BASELINE = {
    "version": "v0.3.1",
    "supersedes": "v0.3 package/index only; technical design unchanged",
    "prepared_CST": "2026-11-16T02:06:08.161610+08:00",
    "zip_sha256": "aecc9c4a5a87f9597628cacce3fab088abd0d4d34f0a02417bad1946d74e6f6a",
    
    "status": {
        "document_responses_implemented": 10,
        "independent_document_corrections_accepted": 10,  # v0.3.1: ALL ACCEPTED
        "independent_acceptance_scope": "DOCUMENT_CORRECTION_ONLY_ENGINEERING10OPEN_PHYSICAL_NOT_RUN",
        "physical_tests": "NOT_RUN",
        "procurement": "NOT_READY",
        "field_array": "NOT_SELECTED",
        "product_release": "NOT_READY",
        "lab_execution": "HOLD",
        "continuous_field_temperature_accuracy": "NOT_PROVEN",
        "cost_or_technical_competitiveness": "UNVERIFIED",
    },
    
    "findings_status": {
        # v0.3.1: ALL document corrections ACCEPTED by independent review
        # But engineering still OPEN, physical still NOT_RUN
        "QA-01": {"doc": "IMPLEMENTED", "recheck": "ACCEPTED", "physical": "NOT_RUN", "engineering": "OPEN"},
        "QA-02": {"doc": "IMPLEMENTED", "recheck": "ACCEPTED", "physical": "NOT_RUN", "engineering": "OPEN"},
        "QA-03": {"doc": "IMPLEMENTED", "recheck": "ACCEPTED", "physical": "NOT_RUN", "engineering": "OPEN"},
        "QA-04": {"doc": "IMPLEMENTED", "recheck": "ACCEPTED", "physical": "NOT_RUN", "engineering": "OPEN"},
        "QA-05": {"doc": "IMPLEMENTED", "recheck": "ACCEPTED", "physical": "NOT_RUN", "engineering": "OPEN"},
        "QA-06": {"doc": "IMPLEMENTED", "recheck": "ACCEPTED", "physical": "NOT_RUN", "engineering": "OPEN"},
        "QA-07": {"doc": "IMPLEMENTED", "recheck": "ACCEPTED", "physical": "NOT_RUN", "engineering": "OPEN"},
        "QA-08": {"doc": "IMPLEMENTED", "recheck": "ACCEPTED", "physical": "NOT_RUN", "engineering": "OPEN"},
        "QA-09": {"doc": "IMPLEMENTED", "recheck": "ACCEPTED", "physical": "NOT_RUN", "engineering": "OPEN"},
        "QA-10": {"doc": "IMPLEMENTED", "recheck": "ACCEPTED", "physical": "NOT_RUN", "engineering": "OPEN"},
    },
    
    "gate_logic": {
        "document_correction_alone_can_close_physical_gate": False,
        "all_required_evidence_present": False,
        "authorized_human_release": False,
    },
    
    "availability_proposals": {
        "normal_FAT_pct": 99.5,
        "normal_SAT_pct": 99.0,
        "max_normal_gap_s": 10,
        "after_link_restore_s": 30,
        "after_valid_power_restore_s": 120,
        "approved": False,
    },
    
    "funding": {
        "A0_complete_total": None,  # UNKNOWN
        "A1_complete_total": None,  # UNKNOWN
        "A2_complete_total": None,  # UNKNOWN
        "B32_complete_total": None,  # UNKNOWN - with corrected BOM notes (4x8=32, 8 backup)
        "B64_complete_total": None,  # UNKNOWN
        "unknown_cost_must_not_default_to_zero": True,
    },
    
    "v031_changes": [
        "10/10文档纠正已被独立复审接受",
        "32点BOM两处备注纠正（4×8=32、8备用点）",
        "新增quality/independent_rereview_v0.3/原件",
    ],
}

# Alias for backward compatibility
V03_BASELINE = V031_BASELINE


def get_model_manifest() -> dict[str, Any]:
    """Get complete model manifest for reproducibility."""
    return MODEL_MANIFEST.copy()


def get_v03_baseline() -> dict[str, Any]:
    """Get v0.3 baseline status."""
    return V03_BASELINE.copy()


def verify_model_available() -> dict[str, Any]:
    """Verify model is available and return status."""
    try:
        from transformers import AutoTokenizer
        tokenizer = AutoTokenizer.from_pretrained(
            MODEL_MANIFEST["model_id"],
            revision=MODEL_MANIFEST["model_revision"],
        )
        return {
            "available": True,
            "model_id": MODEL_MANIFEST["model_id"],
            "revision": MODEL_MANIFEST["model_revision"],
            "vocab_size": tokenizer.vocab_size,
        }
    except Exception as e:
        return {
            "available": False,
            "error": str(e),
        }
