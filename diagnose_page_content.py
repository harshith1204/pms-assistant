"""
Diagnostic script to check page content in MongoDB and identify pages with missing content.
Run this to understand why pages have empty content in Qdrant.
"""

import sys
import os
import json
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from qdrant.dbconnection import page_collection
from collections import defaultdict

def analyze_page_content():
    """Analyze all pages in MongoDB to identify content issues."""
    
    print("=" * 80)
    print("📊 PAGE CONTENT ANALYSIS")
    print("=" * 80)
    
    stats = {
        "total": 0,
        "with_content": 0,
        "empty_content": 0,
        "no_content_field": 0,
        "parse_errors": 0,
        "title_only": 0,
    }
    
    sample_empty_pages = []
    sample_with_content = []
    
    documents = page_collection.find({}, {"_id": 1, "title": 1, "content": 1, "project": 1})
    
    for doc in documents:
        stats["total"] += 1
        title = doc.get("title", "Untitled")
        content = doc.get("content")
        project_name = "Unknown"
        if doc.get("project") and isinstance(doc["project"], dict):
            project_name = doc["project"].get("name", "Unknown")
        
        # Check if content field exists
        if content is None:
            stats["no_content_field"] += 1
            if len(sample_empty_pages) < 5:
                sample_empty_pages.append({
                    "title": title,
                    "project": project_name,
                    "issue": "No content field",
                    "raw_content": None
                })
            continue
        
        # Try to parse EditorJS content
        try:
            if not content or not content.strip():
                stats["empty_content"] += 1
                if len(sample_empty_pages) < 5:
                    sample_empty_pages.append({
                        "title": title,
                        "project": project_name,
                        "issue": "Empty string",
                        "raw_content": content
                    })
                continue
            
            # Parse EditorJS
            content_json = json.loads(content)
            blocks = content_json.get("blocks", [])
            
            # Extract text from blocks
            block_texts = []
            for block in blocks:
                data = block.get("data", {})
                text = data.get("text", "").strip()
                if text:
                    block_texts.append(text)
            
            combined_text = " ".join(block_texts).strip()
            
            if combined_text:
                stats["with_content"] += 1
                if len(sample_with_content) < 3:
                    sample_with_content.append({
                        "title": title,
                        "project": project_name,
                        "content_length": len(combined_text),
                        "content_preview": combined_text[:100] + ("..." if len(combined_text) > 100 else "")
                    })
            else:
                stats["title_only"] += 1
                if len(sample_empty_pages) < 5:
                    sample_empty_pages.append({
                        "title": title,
                        "project": project_name,
                        "issue": "EditorJS blocks have no text",
                        "blocks": len(blocks),
                        "raw_content": content[:200] + "..." if len(content) > 200 else content
                    })
        
        except json.JSONDecodeError as e:
            stats["parse_errors"] += 1
            if len(sample_empty_pages) < 5:
                sample_empty_pages.append({
                    "title": title,
                    "project": project_name,
                    "issue": f"JSON parse error: {str(e)}",
                    "raw_content": str(content)[:200] + "..." if len(str(content)) > 200 else str(content)
                })
        except Exception as e:
            stats["parse_errors"] += 1
            if len(sample_empty_pages) < 5:
                sample_empty_pages.append({
                    "title": title,
                    "project": project_name,
                    "issue": f"Error: {str(e)}",
                    "raw_content": str(content)[:200] + "..." if len(str(content)) > 200 else str(content)
                })
    
    # Print statistics
    print("\n📈 STATISTICS:")
    print(f"  Total pages: {stats['total']}")
    print(f"  Pages with content: {stats['with_content']} ({stats['with_content']/stats['total']*100:.1f}%)")
    print(f"  Pages with no content field: {stats['no_content_field']} ({stats['no_content_field']/stats['total']*100:.1f}%)")
    print(f"  Pages with empty content: {stats['empty_content']} ({stats['empty_content']/stats['total']*100:.1f}%)")
    print(f"  Pages with title only: {stats['title_only']} ({stats['title_only']/stats['total']*100:.1f}%)")
    print(f"  Pages with parse errors: {stats['parse_errors']} ({stats['parse_errors']/stats['total']*100:.1f}%)")
    
    # Show samples
    if sample_with_content:
        print("\n✅ SAMPLE PAGES WITH CONTENT:")
        for i, page in enumerate(sample_with_content, 1):
            print(f"  [{i}] '{page['title']}' (Project: {page['project']})")
            print(f"      Content length: {page['content_length']} chars")
            print(f"      Preview: {page['content_preview']}\n")
    
    if sample_empty_pages:
        print("\n⚠️  SAMPLE PAGES WITH ISSUES:")
        for i, page in enumerate(sample_empty_pages, 1):
            print(f"  [{i}] '{page['title']}' (Project: {page['project']})")
            print(f"      Issue: {page['issue']}")
            if page.get("blocks") is not None:
                print(f"      Blocks: {page['blocks']}")
            if page.get("raw_content"):
                print(f"      Raw content: {page['raw_content']}\n")
            else:
                print()
    
    print("\n💡 RECOMMENDATIONS:")
    if stats['empty_content'] > 0 or stats['no_content_field'] > 0 or stats['title_only'] > 0:
        print("  • Many pages have missing or empty content in MongoDB")
        print("  • Check your page creation process - content may not be saving properly")
        print("  • Pages are being indexed with title as fallback content")
        print("  • Consider adding actual content to these pages in your application")
    
    if stats['parse_errors'] > 0:
        print("  • Some pages have malformed EditorJS content")
        print("  • Check the content format in MongoDB - should be valid EditorJS JSON")
    
    if stats['with_content'] < stats['total'] * 0.3:
        print("  • Less than 30% of pages have actual content")
        print("  • RAG search will be limited without meaningful content to search")
    
    print("\n🔧 NEXT STEPS:")
    print("  1. Fix content in MongoDB by adding actual text to pages")
    print("  2. Re-run indexing: python qdrant/insertdocs.py")
    print("  3. RAG search will then return actual content instead of titles")
    
    print("=" * 80)

if __name__ == "__main__":
    analyze_page_content()
