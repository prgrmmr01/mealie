import bs4

MAX_SOURCE_CONTENT_LENGTH = 100_000
"""
Upper bound on how much source text is sent to an AI provider.

Webpages and pasted content are unbounded, and every character costs tokens, so we cut off
anything beyond a length that comfortably fits even a very long recipe.
"""

TRUNCATION_NOTICE = "\n\n[content truncated]"


def truncate_source_content(content: str, max_length: int = MAX_SOURCE_CONTENT_LENGTH) -> str:
    """Caps source content, marking it so the model knows the text is incomplete."""

    if len(content) <= max_length:
        return content

    return content[:max_length] + TRUNCATION_NOTICE


def truncate_source_parts(parts: list[str], max_length: int = MAX_SOURCE_CONTENT_LENGTH) -> list[str]:
    """
    Caps a group of source texts so that their combined length fits `max_length`.

    Each part is allotted an equal share of the budget, and whatever the shorter parts leave
    unused is handed to the longer ones. Truncating the parts as one string instead would let a
    long webpage swallow the whole budget and drop the text pasted alongside it entirely.
    """

    budgets = [0] * len(parts)
    remaining = max_length

    # shortest first, so that whatever a short part doesn't need is still up for grabs
    for position, index in enumerate(sorted(range(len(parts)), key=lambda index: len(parts[index]))):
        budgets[index] = min(len(parts[index]), remaining // (len(parts) - position))
        remaining -= budgets[index]

    return [truncate_source_content(part, budget) for part, budget in zip(parts, budgets, strict=True)]


def extract_json_ld_data_from_html(soup: bs4.BeautifulSoup) -> str:
    data_parts: list[str] = []
    for script in soup.find_all("script", type="application/ld+json"):
        try:
            script_data = script.string
            if script_data:
                data_parts.append(str(script_data))
        except AttributeError:
            pass

    return "\n\n".join(data_parts)


def find_image(soup: bs4.BeautifulSoup) -> str | None:
    # find the open graph image tag
    og_image = soup.find("meta", property="og:image")
    if og_image and og_image.get("content"):
        return og_image["content"]

    twitter_image = soup.find("meta", attrs={"name": "twitter:image"})
    if twitter_image and twitter_image.get("content"):
        return twitter_image["content"]

    # find the largest image on the page
    largest_img = None
    max_size = 0
    for img in soup.find_all("img"):
        width = img.get("width", 0)
        height = img.get("height", 0)
        if not width or not height:
            continue

        try:
            size = int(width) * int(height)
        except ValueError, TypeError:
            size = 1
        if size > max_size:
            max_size = size
            largest_img = img

    if largest_img:
        return largest_img.get("src")

    return None


def extract_metadata_content_from_html(soup: bs4.BeautifulSoup) -> str:
    """
    Extracts rich recipe descriptions, captions, and notes commonly embedded in social media
    (Facebook, Instagram, TikTok, Pinterest, YouTube) meta tags and oEmbed links.
    """
    meta_parts: list[str] = []
    seen: set[str] = set()

    def add_meta(content: str | None, source_label: str) -> None:
        if not content:
            return
        cleaned = content.strip()
        if len(cleaned) < 20 or cleaned in seen:
            return
        seen.add(cleaned)
        meta_parts.append(f"[{source_label}]:\n{cleaned}")

    # 1. oEmbed title (used by Facebook Reels/Videos to carry the entire post text)
    for link in soup.find_all("link", rel=lambda r: r and "alternate" in r):
        link_type = link.get("type", "")
        if "oembed" in link_type and link.get("title"):
            add_meta(link.get("title"), "Post Caption (oEmbed)")

    # 2. OpenGraph tags
    for prop in ["og:title", "og:description", "og:image:alt"]:
        tag = soup.find("meta", property=prop)
        if tag and tag.get("content"):
            add_meta(tag["content"], f"OpenGraph ({prop})")

    # 3. Twitter card tags
    for name in ["twitter:title", "twitter:description", "twitter:image:alt"]:
        tag = soup.find("meta", attrs={"name": name})
        if tag and tag.get("content"):
            add_meta(tag["content"], f"Twitter ({name})")

    # 4. Standard description
    std_desc = soup.find("meta", attrs={"name": "description"})
    if std_desc and std_desc.get("content"):
        add_meta(std_desc["content"], "Meta Description")

    if not meta_parts:
        return ""

    return "\n\n--- Social Media / Metadata Post Details ---\n" + "\n\n".join(meta_parts)


def extract_page_content(html: str) -> tuple[str, str | None]:
    """
    Strips an HTML document down to its text content, with any ld+json data and
    social media/metadata post details appended, along with the page's primary image.

    Raises if the document contains neither text, metadata, nor ld+json data.
    """

    soup = bs4.BeautifulSoup(html, "lxml")

    body_text = soup.get_text(separator="\n", strip=True)
    json_ld = extract_json_ld_data_from_html(soup)
    meta_text = extract_metadata_content_from_html(soup)

    text_parts = [p for p in [body_text, json_ld, meta_text] if p]
    text = "\n\n".join(text_parts)
    if not text:
        raise ValueError("No text or ld+json data found in HTML")

    try:
        image = find_image(soup)
    except Exception:
        image = None

    return text, image
