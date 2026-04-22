# 本地协议逆向 / 抓包分析沙箱（不含浏览器，只跑分析与脱敏脚本）
FROM python:3.11-slim
WORKDIR /lab
RUN pip install --no-cache-dir requests
COPY extract_login_context.py .
ENV MITM_JSONL=/data/mitm_ufo_flows.jsonl
ENV LAB_OUT=/lab/out
CMD ["python", "extract_login_context.py"]
