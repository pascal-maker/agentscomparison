#!/usr/bin/env python3
"""
Trackio Experiment Tracking Example
Demonstrates how to use Trackio for tracking agent performance and experiments.
"""

import trackio as wandb
import random
import time
import os
from datetime import datetime

def simulate_agent_experiment(agent_name, num_runs=5, epochs=10):
    """
    Simulate an agent experiment with Trackio logging.
    """
    print(f"🤖 Starting experiment for {agent_name}")
    
    # Initialize Trackio for this experiment
    wandb.init(
        project="agents-comparison",
        space_id="pascal-maker/agentscomparison-dashboard",
        config={
            "agent_name": agent_name,
            "num_runs": num_runs,
            "epochs": epochs,
            "learning_rate": 0.001,
            "batch_size": 32,
            "model_type": "transformer",
            "timestamp": datetime.now().isoformat()
        }
    )
    
    for run in range(num_runs):
        print(f"  Run {run + 1}/{num_runs}")
        
        for epoch in range(epochs):
            # Simulate training metrics
            train_loss = random.uniform(0.1, 0.8)
            train_accuracy = random.uniform(0.7, 0.95)
            response_time = random.uniform(0.5, 2.0)
            
            # Simulate validation metrics
            val_loss = train_loss - random.uniform(0.01, 0.1)
            val_accuracy = train_accuracy + random.uniform(0.01, 0.05)
            
            # Simulate agent-specific metrics
            if "gemini" in agent_name.lower():
                api_calls = random.randint(1, 5)
                token_usage = random.randint(100, 1000)
            elif "qwen" in agent_name.lower():
                api_calls = random.randint(1, 3)
                token_usage = random.randint(80, 800)
            else:
                api_calls = random.randint(1, 4)
                token_usage = random.randint(90, 900)
            
            # Log metrics to Trackio
            wandb.log({
                "run_number": run,
                "epoch": epoch,
                "train_loss": train_loss,
                "train_accuracy": train_accuracy,
                "val_loss": val_loss,
                "val_accuracy": val_accuracy,
                "response_time": response_time,
                "api_calls": api_calls,
                "token_usage": token_usage,
                "learning_rate": 0.001 * (0.95 ** epoch),  # Simulate learning rate decay
            })
            
            time.sleep(0.1)  # Simulate processing time
    
    # Log final summary metrics
    wandb.log({
        "final_train_accuracy": random.uniform(0.85, 0.95),
        "final_val_accuracy": random.uniform(0.88, 0.97),
        "total_training_time": random.uniform(60, 300),
        "model_size_mb": random.uniform(100, 500)
    })
    
    wandb.finish()
    print(f"✅ Completed experiment for {agent_name}")

def compare_agents():
    """
    Run experiments for multiple agents and compare their performance.
    """
    agents = [
        "Gemini-MCP-Agent",
        "Qwen-Agent", 
        "DeepSeek-Energy-Agent",
        "Mem0-Energy-Assistant"
    ]
    
    print("🚀 Starting Agent Comparison Experiments")
    print("=" * 50)
    
    for agent in agents:
        simulate_agent_experiment(agent, num_runs=3, epochs=8)
        print()
    
    print("🎉 All experiments completed!")
    print("\n📊 To view the dashboard, run:")
    print("   trackio show")
    print("   or")
    print("   trackio show --project 'agents-comparison'")

def real_agent_tracking_example():
    """
    Example of how to integrate Trackio with actual agent calls.
    """
    print("🔧 Real Agent Tracking Example")
    
    # Initialize tracking for a real experiment
    wandb.init(
        project="real-agent-testing",
        space_id="pascal-maker/agentscomparison-dashboard",
        config={
            "test_type": "response_quality",
            "num_queries": 10,
            "agent_type": "gemini_mcp"
        }
    )
    
    # Simulate real agent interactions
    test_queries = [
        "What is machine learning?",
        "Explain neural networks",
        "How does attention work?",
        "What are transformers?",
        "Explain backpropagation"
    ]
    
    for i, query in enumerate(test_queries):
        # Simulate agent response time
        response_time = random.uniform(0.5, 3.0)
        
        # Simulate response quality metrics
        relevance_score = random.uniform(0.7, 0.95)
        completeness_score = random.uniform(0.6, 0.9)
        accuracy_score = random.uniform(0.8, 0.95)
        
        # Log the interaction
        wandb.log({
            "query_id": i,
            "query": query,
            "response_time": response_time,
            "relevance_score": relevance_score,
            "completeness_score": completeness_score,
            "accuracy_score": accuracy_score,
            "overall_score": (relevance_score + completeness_score + accuracy_score) / 3
        })
        
        time.sleep(0.2)
    
    wandb.finish()
    print("✅ Real agent tracking example completed!")

if __name__ == "__main__":
    # First, install trackio if not already installed
    try:
        import trackio
        print("✅ Trackio is already installed")
    except ImportError:
        print("📦 Installing Trackio...")
        os.system("pip install trackio")
        print("✅ Trackio installed successfully")
    
    print("\n" + "="*60)
    print("🎯 TRACKIO EXPERIMENT TRACKING DEMO")
    print("="*60)
    
    # Run the comparison experiments
    compare_agents()
    
    print("\n" + "="*60)
    
    # Run real agent tracking example
    real_agent_tracking_example()
    
    print("\n" + "="*60)
    print("🎉 Setup Complete!")
    print("\n📋 Next Steps:")
    print("1. Run 'trackio show' to view your experiments")
    print("2. Integrate Trackio into your actual agent code")
    print("3. Deploy dashboard to Hugging Face Spaces if desired")
    print("\n💡 Tip: You can embed the dashboard in websites using iframes!") 