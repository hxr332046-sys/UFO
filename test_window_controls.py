#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Get detailed control information from desktop windows using UFO's UI automation."""

import asyncio
import json
import sys
import os

# Add UFO to path
sys.path.insert(0, r"D:\UFO")


async def main():
    from ufo.automator.ui_control import UIControl
    
    ctrl = UIControl()
    
    # Get all open applications
    print("=" * 70)
    print("  Desktop Applications & Window Control Details")
    print("=" * 70)
    
    apps = ctrl.get_opened_application()
    print(f"\nFound {len(apps)} application windows:\n")
    
    for i, app in enumerate(apps):
        pid = app.get("pid", "?")
        name = app.get("name", "?")
        title = app.get("title", "")[:80]
        app_type = app.get("type", "?")
        print(f"  [{i}] PID={pid}  Name={name}  Type={app_type}")
        print(f"      Title: {title}")
    
    # Now get control details for each visible window
    print("\n" + "=" * 70)
    print("  Window Control Trees (UI Elements)")
    print("=" * 70)
    
    for i, app in enumerate(apps[:10]):  # Limit to first 10
        pid = app.get("pid", "?")
        name = app.get("name", "?")
        title = app.get("title", "")[:60]
        
        print(f"\n{'─' * 60}")
        print(f"  [{i}] {name} (PID={pid}) — {title}")
        print(f"{'─' * 60}")
        
        try:
            # Get control items for this application
            controls = ctrl.get_control_item_for_app(app, skip_redundant=True)
            
            if not controls:
                print("    (No controls found)")
                continue
            
            # Group controls by type
            by_type = {}
            for c in controls:
                ctype = c.get("control_type", "Unknown")
                if ctype not in by_type:
                    by_type[ctype] = []
                by_type[ctype].append(c)
            
            # Print summary
            print(f"    Total controls: {len(controls)}")
            for ctype, items in sorted(by_type.items(), key=lambda x: -len(x[1])):
                print(f"    {ctype}: {len(items)}")
            
            # Print notable controls with text
            print(f"\n    Notable UI elements:")
            shown = 0
            for c in controls:
                name_val = c.get("name", "")
                ctype = c.get("control_type", "")
                automation_id = c.get("automation_id", "")
                value = c.get("value", "")
                
                # Only show controls with meaningful text
                display = name_val or value or automation_id
                if display and shown < 20:
                    detail = name_val or value
                    if automation_id:
                        detail += f" [id={automation_id}]"
                    print(f"      {ctype}: {detail[:70]}")
                    shown += 1
            
            if shown >= 20:
                remaining = len([c for c in controls if c.get("name") or c.get("value")]) - shown
                if remaining > 0:
                    print(f"      ... and {remaining} more elements with text")
                    
        except Exception as e:
            print(f"    Error getting controls: {e}")


if __name__ == "__main__":
    asyncio.run(main())
