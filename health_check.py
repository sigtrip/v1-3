import os
import sys
from datetime import datetime

def run_diag():
    print(f'--- ARGOS SYSTEM DIAGNOSTIC [{datetime.now()}] ---')
    
    # 1. Check ML Model
    model_path = 'data/argos_model/argos_intent_model.pkl'
    if os.path.exists(model_path):
        print(f'✅ ML Model: Found ({os.path.getsize(model_path)//1024} KB)')
    else:
        print('❌ ML Model: Missing')
        
    # 2. Check AI Modules
    try:
        from src.ai.web_search import WebIntelligence
        print('✅ WebIntelligence: Loaded')
    except Exception as e:
        print(f'❌ WebIntelligence: Failed to load ({e})')

    # 3. Check Core Integrity
    core_path = 'src/core.py'
    if os.path.exists(core_path):
        with open(core_path, 'r') as f:
            content = f.read()
            if 'NeuralNexus' in content:
                print('✅ Core Patch: Applied (NeuralNexus)')
            else:
                print('⚠️ Core Patch: Missing NeuralNexus integration')

if __name__ == "__main__":
    run_diag()