# 本文件是可提交的本地 Demo 环境模板；不要在这里填写真实密钥。
# 复制为 env.md 后再修改：cp env.example.md env.md

source .venv/bin/activate

export MODEL_PROVIDER=deepseek
export MODEL_BASE_URL=https://api.deepseek.com
export MODEL_NAME=deepseek-v4-flash
export MODEL_API_KEY=
export MODEL_STREAMING=true
# 与真实 DeepSeek Flash 延迟匹配的意图识别超时（秒）。
export INTENT_CLASSIFY_TIMEOUT_SECONDS=15

# 使用本地中文语义向量（FastEmbed，Apache-2.0，本机 ONNX）。
# 不是 Pinecone / Weaviate / 付费 embedding API。完全离线 Demo 可改为 hash。
export RAG_EMBEDDING_PROVIDER=fastembed
export RAG_EMBEDDING_MODEL=BAAI/bge-small-zh-v1.5

# 默认复用 MODEL_API_KEY 和 MODEL_BASE_URL；只有视觉模型使用独立服务时才取消注释。
export VISION_MODEL_NAME=deepseek-v4-flash-vision-exp
export BUSINESS_DOMAIN=ecommerce
# export VISION_BASE_URL=https://api.example.com
# export VISION_API_KEY=replace-me
