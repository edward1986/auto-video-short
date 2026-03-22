# scripts/update_readme.py
import feedparser

# RSS Feed URL
RSS_FEED_URL = "http://multiculturaltoolbox.com/rss2.xml"

# Parse the RSS feed
feed = feedparser.parse(RSS_FEED_URL)

# Extract latest posts
latest_posts = []
for entry in feed.entries[:100]:  # Limit to 5 latest posts
    title = entry.title
    link = entry.link
    description = entry.description.replace("<p>", "").replace("</p>", "").strip()
    image_url = entry.enclosures[0].href if entry.enclosures else ""

    # Extract YouTube video ID if present
    video_id = None
    if 'youtube.com/embed/' in description:
        start_index = description.find('youtube.com/embed/') + 18
        end_index = description.find('?si=', start_index)
        video_id = description[start_index:end_index] if end_index != -1 else None

    latest_posts.append({
        "title": title,
        "link": link,
        "description": description[:200] + "...",  # Limit to 200 chars for readability
        "image_url": image_url,
        "video_id": video_id
    })

# Read the current README file
with open("README.md", "r") as readme_file:
    readme_content = readme_file.readlines()

# Identify where to insert the new content
start_marker = "<!-- BLOG-POSTS-START -->"
end_marker = "<!-- BLOG-POSTS-END -->"
start_index = next((i for i, line in enumerate(readme_content) if start_marker in line), None)
end_index = next((i for i, line in enumerate(readme_content) if end_marker in line), None)

# Generate new blog section content
new_content = [start_marker + "\n"]
new_content.append("## 📢 Latest Blog Posts from MultiCulturalToolbox\n")
for post in latest_posts:
    new_content.append(f"### [{post['title']}]({post['link']})\n")
    new_content.append(f"![Thumbnail]({post['image_url']})\n")
    new_content.append(f"**Description:** {post['description']}\n")
    if post['video_id']:
        new_content.append(f"[🎥 Watch Video](https://www.youtube.com/watch?v={post['video_id']})\n")
    new_content.append("\n---\n")

new_content.append(end_marker + "\n")

# Update README.md with new content
if start_index is not None and end_index is not None:
    updated_content = readme_content[:start_index+1] + new_content + readme_content[end_index:]
else:
    updated_content = readme_content + ["\n"] + new_content

# Write back to README.md
with open("README.md", "w") as readme_file:
    readme_file.writelines(updated_content)

print("✅ README.md updated successfully!")
