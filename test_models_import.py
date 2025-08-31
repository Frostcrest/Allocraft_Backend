#!/usr/bin/env python3
"""
Simple test to check if models can be imported
"""
import sys
sys.path.append('/opt/render/project/src/fastapi_project')

try:
    from app import models
    print("✅ Models imported successfully")
    print(f"✅ Available models: {dir(models)}")
    
    if hasattr(models, 'Ticker'):
        print("✅ Ticker model found")
    else:
        print("❌ Ticker model NOT found")
        
    if hasattr(models, 'Stock'):
        print("✅ Stock model found")
    else:
        print("❌ Stock model NOT found")
        
    if hasattr(models, 'Price'):
        print("✅ Price model found")
    else:
        print("❌ Price model NOT found")
        
except Exception as e:
    print(f"❌ Error importing models: {e}")
    import traceback
    traceback.print_exc()
