"""Tests for workflow graph trajectory."""

import pytest

from boiler_fbg_workflow.config import CostLedger, RuntimeDeps, WorkflowSettings
from boiler_fbg_workflow.graph import build_boiler_fbg_graph
from boiler_fbg_workflow.schemas import GateStatus


class TestGraphTrajectory:
    """Test workflow graph execution in simulation mode."""
    
    @pytest.fixture
    def simulation_deps(self):
        """Create simulation mode dependencies."""
        settings = WorkflowSettings(mode="simulation", hitl_enabled=True)
        ledger = CostLedger()
        return RuntimeDeps(settings=settings, ledger=ledger)
    
    def test_graph_builds_successfully(self, simulation_deps):
        """Test that the graph builds without errors."""
        graph = build_boiler_fbg_graph(simulation_deps)
        assert graph is not None
    
    def test_simulation_run_completes(self, simulation_deps):
        """Test that a simulation run completes all stages."""
        graph = build_boiler_fbg_graph(simulation_deps)
        
        initial_state = {
            "run_id": "test-run-001",
            "mode": "simulation",
            "hitl_enabled": True,
            "output_dir": "./outputs/test",
        }
        
        config = {"configurable": {"thread_id": "test-thread"}}
        
        # Collect all events
        events = []
        for event in graph.stream(initial_state, config=config):
            events.append(event)
        
        # Should have multiple events (one per node)
        assert len(events) > 0
        
        # Check that final report was generated
        final_event = events[-1]
        assert "final_report" in final_event
    
    def test_stage_0_outputs(self, simulation_deps):
        """Test Stage 0 simulation outputs."""
        graph = build_boiler_fbg_graph(simulation_deps)
        
        initial_state = {
            "run_id": "test-stage0",
            "mode": "simulation",
            "hitl_enabled": True,
            "output_dir": "./outputs/test",
        }
        
        config = {"configurable": {"thread_id": "test-stage0"}}
        
        # Get first event (stage 0 market research)
        events = list(graph.stream(initial_state, config=config))
        
        # Find stage 0 output
        stage_0_output = None
        for event in events:
            if "stage_0_market_research" in event:
                stage_0_output = event["stage_0_market_research"]
                break
        
        assert stage_0_output is not None
        assert "market_segments" in stage_0_output
        assert "requirements" in stage_0_output
        assert len(stage_0_output["market_segments"]) > 0
    
    def test_qa_review_generated(self, simulation_deps):
        """Test that QA reviews are generated."""
        graph = build_boiler_fbg_graph(simulation_deps)
        
        initial_state = {
            "run_id": "test-qa",
            "mode": "simulation",
            "hitl_enabled": True,
            "output_dir": "./outputs/test",
        }
        
        config = {"configurable": {"thread_id": "test-qa"}}
        
        events = list(graph.stream(initial_state, config=config))
        
        # Find QA review output
        qa_found = False
        for event in events:
            for node_name, output in event.items():
                if "qa_review" in node_name and output:
                    if "qa_reviews" in output:
                        qa_found = True
                        reviews = output["qa_reviews"]
                        assert len(reviews) > 0
                        assert "gate_status" in reviews[0]
        
        assert qa_found, "No QA review found in trajectory"
    
    def test_hitl_decision_generated(self, simulation_deps):
        """Test that HITL decisions are generated."""
        graph = build_boiler_fbg_graph(simulation_deps)
        
        initial_state = {
            "run_id": "test-hitl",
            "mode": "simulation",
            "hitl_enabled": True,
            "output_dir": "./outputs/test",
        }
        
        config = {"configurable": {"thread_id": "test-hitl"}}
        
        events = list(graph.stream(initial_state, config=config))
        
        # Find HITL decision output
        hitl_found = False
        for event in events:
            for node_name, output in event.items():
                if "hitl" in node_name and output:
                    if "hitl_decisions" in output:
                        hitl_found = True
                        decisions = output["hitl_decisions"]
                        assert len(decisions) > 0
                        assert decisions[0]["decision"] == "approve"  # Simulation auto-approves
        
        assert hitl_found, "No HITL decision found in trajectory"
    
    def test_telemetry_events_collected(self, simulation_deps):
        """Test that telemetry events are collected."""
        graph = build_boiler_fbg_graph(simulation_deps)
        
        initial_state = {
            "run_id": "test-telemetry",
            "mode": "simulation",
            "hitl_enabled": True,
            "output_dir": "./outputs/test",
        }
        
        config = {"configurable": {"thread_id": "test-telemetry"}}
        
        events = list(graph.stream(initial_state, config=config))
        
        # Count telemetry events
        telemetry_count = 0
        for event in events:
            for node_name, output in event.items():
                if output and "telemetry_events" in output:
                    telemetry_count += len(output["telemetry_events"])
        
        assert telemetry_count > 0, "No telemetry events collected"


class TestGraphEdgeCases:
    """Test edge cases and error handling."""
    
    @pytest.fixture
    def simulation_deps(self):
        settings = WorkflowSettings(mode="simulation", hitl_enabled=True)
        ledger = CostLedger()
        return RuntimeDeps(settings=settings, ledger=ledger)
    
    def test_empty_initial_state(self, simulation_deps):
        """Test handling of minimal initial state."""
        graph = build_boiler_fbg_graph(simulation_deps)
        
        # Minimal state
        initial_state = {
            "run_id": "test-minimal",
            "mode": "simulation",
        }
        
        config = {"configurable": {"thread_id": "test-minimal"}}
        
        # Should still complete
        events = list(graph.stream(initial_state, config=config))
        assert len(events) > 0
    
    def test_multiple_runs_isolated(self, simulation_deps):
        """Test that multiple runs are isolated."""
        graph = build_boiler_fbg_graph(simulation_deps)
        
        # Run 1
        state1 = {"run_id": "run-1", "mode": "simulation"}
        config1 = {"configurable": {"thread_id": "thread-1"}}
        events1 = list(graph.stream(state1, config=config1))
        
        # Run 2
        state2 = {"run_id": "run-2", "mode": "simulation"}
        config2 = {"configurable": {"thread_id": "thread-2"}}
        events2 = list(graph.stream(state2, config=config2))
        
        # Both should complete independently
        assert len(events1) > 0
        assert len(events2) > 0
