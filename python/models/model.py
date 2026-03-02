"""
Mesa ABM Simulation Model

This module implements the core simulation model using Mesa framework.
"""

from mesa import Model
from mesa.time import RandomActivation
from mesa.datacollection import DataCollector

import networkx as nx
import numpy as np

from ..agents.agent import Agent, AgentProfile
from ..networks.generator import generate_network, compute_network_metrics
from ..config.settings import SimulationConfig


class DiffusionModel(Model):
    """
    Agent-Based Model for New Product Diffusion.
    
    Attributes:
        config: Simulation configuration
        network: NetworkX graph representing social network
        agents: Dictionary of agent_id -> Agent
        running: Boolean indicating if simulation is running
        current_step: Current simulation step
        datacollector: Mesa data collector for metrics
    """
    
    def __init__(self, config: SimulationConfig):
        """
        Initialize the diffusion model.
        
        Args:
            config: Simulation configuration
        """
        super().__init__()
        
        self.config = config
        self.current_step = 0
        self.running = True
        
        # Generate network
        self.network = generate_network(
            network_type=config.network_type,
            n_nodes=config.n_agents,
            avg_degree=config.avg_degree,
            rewiring_prob=config.rewiring_prob,
            seed=config.seed,
        )
        
        # Compute network metrics
        self.network_metrics = compute_network_metrics(self.network)
        
        # Initialize agents
        self.agents = {}
        self._initialize_agents()
        
        # Set up scheduler
        self.schedule = RandomActivation(self)
        for agent in self.agents.values():
            self.schedule.add(agent)
        
        # Set up data collector
        self.datacollector = DataCollector(
            model_reporters={
                "total_adopters": lambda m: sum(1 for a in m.agents.values() if a.memory.has_adopted),
                "adoption_rate": lambda m: sum(1 for a in m.agents.values() if a.memory.has_adopted) / m.config.n_agents,
                "cumulative_adoption": lambda m: self._compute_cumulative_adoption(),
            },
            agent_reporters={
                "has_adopted": lambda a: a.memory.has_adopted,
                "adoption_time": lambda a: a.memory.adoption_time,
                "wom_count": lambda a: len(a.memory.wom_received),
            }
        )
    
    def _initialize_agents(self) -> None:
        """Initialize all agents with unique IDs and profiles."""
        for node_id in self.network.nodes():
            profile = AgentProfile(agent_id=node_id)
            agent = Agent(agent_id=node_id, profile=profile)
            self.agents[node_id] = agent
    
    def _compute_cumulative_adoption(self) -> list[int]:
        """Compute cumulative adoption over time."""
        adoption_times = [
            a.memory.adoption_time 
            for a in self.agents.values() 
            if a.memory.adoption_time is not None
        ]
        
        cumulative = []
        for t in range(self.current_step + 1):
            count = sum(1 for time in adoption_times if time <= t)
            cumulative.append(count)
        
        return cumulative
    
    def get_neighbors(self, agent_id: int) -> list[int]:
        """
        Get neighbor agent IDs.
        
        Args:
            agent_id: Agent ID
            
        Returns:
            List of neighbor IDs
        """
        return list(self.network.neighbors(agent_id))
    
    def get_adopted_neighbors(self, agent_id: int) -> list[int]:
        """
        Get adopted neighbor agent IDs.
        
        Args:
            agent_id: Agent ID
            
        Returns:
            List of adopted neighbor IDs
        """
        neighbors = self.get_neighbors(agent_id)
        return [
            nid for nid in neighbors 
            if self.agents[nid].memory.has_adopted
        ]
    
    def step(self) -> None:
        """
        Execute one simulation step.
        
        Each step:
        1. Activate all agents (make adoption/transmission decisions)
        2. Collect data
        3. Increment step counter
        4. Check termination condition
        """
        self.schedule.step()
        self.datacollector.collect(self)
        self.current_step += 1
        
        # Termination: all agents adopted or max steps reached
        total_adopters = sum(1 for a in self.agents.values() if a.memory.has_adopted)
        if total_adopters >= self.config.n_agents or self.current_step >= self.config.n_steps:
            self.running = False
    
    def get_metrics(self) -> dict:
        """
        Get final simulation metrics.
        
        Returns:
            Dictionary of metrics
        """
        adopters = [a for a in self.agents.values() if a.memory.has_adopted]
        adoption_times = [a.memory.adoption_time for a in adopters if a.memory.adoption_time is not None]
        
        metrics = {
            "total_adopters": len(adopters),
            "final_adoption_rate": len(adopters) / self.config.n_agents,
            "avg_adoption_time": np.mean(adoption_times) if adoption_times else None,
            "median_adoption_time": np.median(adoption_times) if adoption_times else None,
            "network_metrics": self.network_metrics,
            "config": {
                "network_type": self.config.network_type,
                "wom_strength": self.config.wom_strength,
                "n_agents": self.config.n_agents,
                "n_steps": self.config.n_steps,
            }
        }
        
        return metrics


__all__ = ["DiffusionModel"]
