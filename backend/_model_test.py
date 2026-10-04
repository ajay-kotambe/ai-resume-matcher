from sentence_transformers import SentenceTransformer
m = SentenceTransformer("sentence-transformers/all-MiniLM-L6-v2")
v = m.encode(["hello world", "resume parsing"])
print("MODEL_OK dim=", v.shape)
