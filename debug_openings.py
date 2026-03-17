#!/usr/bin/env python3

import sys
sys.path.insert(0, '/app/backend')

from coach_engine.opening_plans import build_opening_coaching_context
from services.move_by_move_coach import get_variation_teaching

# Test Sicilian
print("=== TESTING SICILIAN ===")
moves = ["e4", "c5", "Nf3", "d6", "d4", "cxd4", "Nxd4", "Nf6", "Nc3", "a6"]
context = build_opening_coaching_context(moves)
print(f"Context name: {context['name'] if context else None}")

if context:
    print(f"Variations available: {list(context.get('variations', {}).keys())}")
    teaching = get_variation_teaching(moves, context, "black")
    if teaching:
        print(f"Variation name: {teaching['variation_name']}")
        print(f"Plans for user: {teaching.get('plans_for_user', [])}")
    else:
        print("No teaching found")
else:
    print("No context found")

print("\n=== TESTING CARO-KANN ===")
moves2 = ["e4", "c6", "d4", "d5", "Nc3", "dxe4", "Nxe4", "Bf5"]
context2 = build_opening_coaching_context(moves2)
if context2:
    teaching2 = get_variation_teaching(moves2, context2, "black")
    if teaching2:
        print(f"Variation name: {teaching2['variation_name']}")
        print(f"Plans for user: {teaching2.get('plans_for_user', [])}")
        print(f"Key plans: {teaching2.get('key_plans', [])}")
    else:
        print("No teaching found")