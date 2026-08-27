# 本文件是可提交的本地 Demo 环境模板；不要在这里填写真实密钥。
# 复制为 env.md 后再修改：cp env.example.md env.md

source .venv/bin/activate

export MODEL_PROVIDER=deepseek
export MODEL_BASE_URL=https://api.deepseek.com
export MODEL_NAME=deepseek-v4-flash
export MODEL_API_KEY=
export MODEL_STREAMING=true

# 默认复用 MODEL_API_KEY 和 MODEL_BASE_URL；只有视觉模型使用独立服务时才取消注释。
export VISION_MODEL_NAME=deepseek-v4-flash-vision-exp
# export VISION_BASE_URL=https://api.example.com
# export VISION_API_KEY=replace-me
