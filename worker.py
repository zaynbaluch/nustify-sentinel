from core.scraper import scrape_page
from core.utils import get_text_hash
from core.analyzer import llm_analyze_change
from core.notifier import send_alert
from core.db import supabase

def job():
    print("🔹 Job started: fetching monitored pages from database...")
    sources = supabase.table("monitored_pages").select("*").execute().data
    print(f"🔹 {len(sources)} pages fetched for monitoring.\n")

    pages_with_changes = []  # Collect pages that had meaningful changes
    pages_checked = []       # Collect all page names for reference

    for idx, s in enumerate(sources, start=1):
        print(f"🟢 Checking page {idx}/{len(sources)}: {s['name']} ({s['url']})")
        content = scrape_page(s["url"])
        if not content:
            print(f"⚠️ Failed to fetch content for {s['name']}, skipping.\n")
            continue

        pages_checked.append(s["name"])  # Track pages checked

        new_hash = get_text_hash(content)
        if new_hash != s["content_hash"]:
            print(f"🔍 Change detected for {s['name']}, analyzing with LLM...")
            analysis = llm_analyze_change(s["last_content"], content)

            # Only consider pages with meaningful changes
            if analysis.get("is_meaningful"):
                print(f"✅ Meaningful change detected for {s['name']}. Sending alert...")
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

                # Send individual alert for meaningful change
                send_alert(s["name"], analysis["summary"], s["url"])
                pages_with_changes.append(s["name"])
            else:
                print(f"ℹ️ Change detected for {s['name']}, but not meaningful.\n")
        else:
            print(f"ℹ️ No change detected for {s['name']}.\n")

        # Update the monitored page record
        supabase.table("monitored_pages").update({
            "last_content": content,
            "content_hash": new_hash,
            "last_checked": "now()"
        }).eq("id", s["id"]).execute()
        print(f"🔹 Updated record for {s['name']}.\n")

    # If no meaningful changes found, send a single “no changes” email
    if not pages_with_changes and pages_checked:
        print("ℹ️ No meaningful changes detected for any monitored page. Sending summary email...")
        summary_text = "No changes were detected for the following monitored pages:\n\n"
        summary_text += "\n".join(f"• {x}\n" for x in pages_checked)
        send_alert("No changes detected", [summary_text], None)
        print("✅ Summary email sent.\n")

    print("🔹 Job completed.")

if __name__ == "__main__":
    job()
