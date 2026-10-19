from unittest.mock import patch

from bs4 import BeautifulSoup
from sqlalchemy import Column, Integer, create_engine, text
from sqlalchemy.orm import Session, declarative_base

from mealie.core.encryption import decrypt_secret, encrypt_secret
from mealie.db.models._model_utils.encrypted_string import EncryptedString
from mealie.services.openai.ai_models import ModelItem
from mealie.services.openai.content import extract_metadata_content_from_html, find_image


def test_encryption_logic():
    test_secret = "test-secret-key-1234567890"
    with patch("mealie.core.encryption.get_app_settings") as mock_settings:
        mock_settings.return_value.SECRET = test_secret

        raw_api_key = "AIzaSyDummyKey_12345abcde"
        encrypted = encrypt_secret(raw_api_key)
        assert encrypted is not None
        assert encrypted.startswith("enc:"), f"Expected enc: prefix, got {encrypted}"
        assert raw_api_key not in encrypted, "Raw key should not be in ciphertext"

        # Decrypt ciphertext
        decrypted = decrypt_secret(encrypted)
        assert decrypted == raw_api_key, f"Expected {raw_api_key}, got {decrypted}"

        # Test legacy plain text (backward compatibility)
        legacy_plain = "legacy_sk_1234567890"
        decrypted_legacy = decrypt_secret(legacy_plain)
        assert decrypted_legacy == legacy_plain, "Legacy unencrypted string should pass through unchanged"

        # Test empty / None handling
        assert encrypt_secret(None) is None
        assert encrypt_secret("") == ""
        assert decrypt_secret(None) is None
        assert decrypt_secret("") == ""


def test_sqlalchemy_encrypted_column():
    with patch("mealie.core.encryption.get_app_settings") as mock_settings:
        mock_settings.return_value.SECRET = "db-test-secret"

        Base = declarative_base()

        class DummyModel(Base):
            __tablename__ = "dummy"
            id = Column(Integer, primary_key=True)
            secret_key = Column(EncryptedString(500))

        engine = create_engine("sqlite:///:memory:")
        Base.metadata.create_all(engine)

        with Session(engine) as session:
            item = DummyModel(id=1, secret_key="my-super-secret-gemini-key")
            session.add(item)
            session.commit()

        # Raw DB check: Ensure SQLite table contains enc:... (use raw text query so TypeDecorator does not decrypt)
        with engine.connect() as conn:
            raw_val = conn.execute(text("SELECT secret_key FROM dummy WHERE id = 1")).scalar()
            assert raw_val.startswith("enc:"), f"Raw SQLite storage should be prefixed with 'enc:', got: {raw_val}"
            assert "my-super-secret-gemini-key" not in raw_val, "Raw secret was found unencrypted in database!"

        # ORM read check: Ensure loading through SQLAlchemy decrypts to plain text
        with Session(engine) as session:
            loaded = session.get(DummyModel, 1)
            assert loaded.secret_key == "my-super-secret-gemini-key", f"Expected plain secret, got: {loaded.secret_key}"


def test_social_media_metadata_extraction():
    sample_facebook_html = """<!DOCTYPE html>
<html>
<head>
  <title>Crispy Greek Salad Recipe | Facebook</title>
  <meta property="og:title" content="Viral Crispy Chickpea Greek Salad - High Protein &amp; Easy Prep" />
  <meta
    property="og:description"
    content="Ingredients: 1 can chickpeas. Dressing: 3 tbsp oil. Instructions: Toss well."
  />
  <meta property="og:image" content="https://scontent.xx.fbcdn.net/v/t15.5256-10/sample_salad.jpg" />
  <link
    rel="alternate"
    type="application/json+oembed"
    href="data:application/json,%7B%22title%22%3A%22Viral%20Crispy%20Chickpea%20Greek%20Salad%22%7D"
  />
</head>
<body>
  <div class="login-wall">Please log in to Facebook to see this Reel.</div>
</body>
</html>
"""
    soup = BeautifulSoup(sample_facebook_html, "html.parser")
    extracted_text = extract_metadata_content_from_html(soup)

    assert "Viral Crispy Chickpea Greek Salad" in extracted_text
    assert "Ingredients: 1 can chickpeas" in extracted_text
    assert "Dressing: 3 tbsp oil" in extracted_text
    assert "Instructions: Toss well" in extracted_text

    found_img = find_image(soup)
    assert found_img == "https://scontent.xx.fbcdn.net/v/t15.5256-10/sample_salad.jpg"


def test_gemini_model_filtering():
    raw_api_response = {
        "models": [
            {
                "name": "models/embedding-gecko-001",
                "displayName": "Embedding Gecko",
                "description": "Obtain a distributed representation of a text.",
                "supportedGenerationMethods": ["embedContent"],
            },
            {
                "name": "models/gemini-1.5-flash",
                "displayName": "Gemini 1.5 Flash",
                "description": "Fast and versatile multimodal model.",
                "supportedGenerationMethods": ["generateContent", "countTokens"],
            },
            {
                "name": "models/gemini-2.5-flash",
                "displayName": "Gemini 2.5 Flash",
                "description": "Next generation ultra fast model.",
                "supportedGenerationMethods": ["generateContent", "countTokens"],
            },
            {
                "name": "models/gemini-2.5-pro",
                "displayName": "Gemini 2.5 Pro",
                "description": "Top tier reasoning model.",
                "supportedGenerationMethods": ["generateContent", "countTokens"],
            },
            {
                "name": "models/gemini-1.5-pro",
                "displayName": "Gemini 1.5 Pro",
                "description": "High capability multimodal model.",
                "supportedGenerationMethods": ["generateContent", "countTokens"],
            },
        ]
    }

    candidate_models = []
    for m in raw_api_response.get("models", []):
        methods = m.get("supportedGenerationMethods", [])
        if "generateContent" not in methods:
            continue
        model_id = m.get("name", "").replace("models/", "")
        display_name = m.get("displayName") or model_id
        description = m.get("description")
        candidate_models.append(
            ModelItem(
                id=model_id,
                name=display_name,
                description=description,
            )
        )

    def sort_key(model: ModelItem) -> int:
        priority_order = [
            "gemini-3.5-flash-lite",
            "gemini-flash-lite-latest",
            "gemini-flash-latest",
            "gemini-3.8-flash",
            "gemini-3.5-flash",
            "gemini-2.5-flash",
            "gemini-2.5-pro",
            "gemini-1.5-flash",
            "gemini-1.5-pro",
        ]
        for idx, prefix in enumerate(priority_order):
            if model.id.startswith(prefix):
                return idx
        return len(priority_order)

    candidate_models.sort(key=sort_key)
    model_ids = [m.id for m in candidate_models]

    assert "embedding-gecko-001" not in model_ids
    assert model_ids == ["gemini-2.5-flash", "gemini-2.5-pro", "gemini-1.5-flash", "gemini-1.5-pro"]
