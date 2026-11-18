#!/usr/bin/env python3
"""
Add a "Key insights" text widget to each Cumulus Overview dashboard template.

Reads atf/insights.json (one entry per dashboard: {"use": ..., "bullets": [...]}). The numbers in it were
computed from live Semantic Query API results on the generated data (seed 42 for the seven original LOBs,
seed 7 for the contact center). If the data is regenerated, re-check them.

Idempotent: if a "summary" widget already exists it is replaced in place. Run it again after atf/build_vizzes.py,
because the builder rewrites the dashboard files.

Usage: python3 atf/add_summary_widgets.py
"""
import json
import os

HERE = os.path.dirname(os.path.abspath(__file__))
TPL = os.path.join(os.path.dirname(HERE), "force-app", "main", "default", "appTemplates")


def main():
    insights = json.load(open(os.path.join(HERE, "insights.json"), encoding="utf-8"))
    for dash, info in insights.items():
        tname = dash.replace("_Overview", "")
        path = os.path.join(TPL, tname, "dashboards", dash + ".json")
        if not os.path.exists(path):
            print("missing", path)
            continue
        d = json.load(open(path, encoding="utf-8"))
        hdr = d["widgets"]["hdr"]["parameters"]["content"]
        title_color = hdr[0]["attributes"]["color"]
        content = [{"attributes": {"color": title_color, "size": "16px", "bold": True}, "insert": f"Key insights: {info['use']}", "rules": []},
                   {"attributes": {"align": "left"}, "insert": "\n", "rules": []}]
        for b in info["bullets"]:
            content += [{"attributes": {"color": "#2E2E2E", "size": "13px"}, "insert": "•  " + b, "rules": []},
                        {"attributes": {"align": "left"}, "insert": "\n", "rules": []}]
        widget = {"actions": [], "name": "summary", "type": "text",
                  "parameters": {"conditionalFormattingRules": [], "receiveFilterSource": {"filterMode": "all", "widgetIds": []}, "content": content,
                                 "widgetStyle": {"backgroundColor": "#FFFFFF", "borderColor": "#E3E9F1", "borderEdges": [], "borderRadius": 16, "borderWidth": 1}}}
        page = d["layouts"][0]["pages"][0]
        h = 3 + len(info["bullets"])
        if "summary" in d["widgets"]:
            d["widgets"]["summary"] = widget
            action = "updated"
        else:
            hp = next(p for p in page["widgets"] if p["name"] == "hdr")
            at = hp["row"] + hp["rowspan"]
            for p in page["widgets"]:
                if p["row"] >= at:
                    p["row"] += h
            page["widgets"].append({"name": "summary", "column": 0, "row": at, "colspan": 96, "rowspan": h})
            d["widgets"]["summary"] = widget
            action = "added"
        json.dump(d, open(path, "w", encoding="utf-8"), indent=2)
        print(f"{dash}: summary widget {action} ({h} rows)")


if __name__ == "__main__":
    main()
