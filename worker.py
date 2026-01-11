from core.scraper import scrape_page
from core.utils import get_text_hash
from core.analyzer import llm_analyze_change
from core.notifier import send_alert
from core.db import supabase

def job():
    sources = supabase.table("monitored_pages").select("*").execute().data

    for s in sources:
        content = scrape_page(s["url"])
        if not content:
            continue

        new_hash = get_text_hash(content)
        if new_hash != s["content_hash"]:
            analysis = llm_analyze_change(s["last_content"], content)
            if analysis.get("is_meaningful"):
                summary = analysis["summary"]
                if isinstance(summary, list):
                    summary = "\n".join(f"• {x}" for x in summary)

                supabase.table("detected_changes").insert({
                    "page_id": s["id"],
                    "title": s["name"],
                    "summary": summary,
                    "is_meaningful": True,
                    "url": s["url"]
                }).execute()

                send_alert(s["name"], analysis["summary"], s["url"])

            supabase.table("monitored_pages").update({
                "last_content": content,
                "content_hash": new_hash,
                "last_checked": "now()"
            }).eq("id", s["id"]).execute()

if __name__ == "__main__":
    job()
