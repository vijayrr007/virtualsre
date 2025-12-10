#!/usr/bin/env python
"""Quick test with OpenAI for natural language responses."""

import os
import sys

# Check if API key is set
if not os.getenv("OPENAI_API_KEY"):
    print("❌ Please set your OpenAI API key:")
    print("   export OPENAI_API_KEY='sk-...'")
    print()
    print("Example:")
    print("   export OPENAI_API_KEY='sk-proj-...'")
    sys.exit(1)

print("✅ OpenAI API key found!")
print("🔄 Testing with OpenAI GPT-4o-mini for natural language responses...")
print()

# Import and run the simple usage functions
try:
    from simple_usage import main
    main()
except ImportError as e:
    print(f"❌ Import error: {e}")
    print()
    print("Make sure you're running with the virtual environment:")
    print("   /Users/vijaymantena/virtualsre/.venv/bin/python test_with_openai.py")
    sys.exit(1)
