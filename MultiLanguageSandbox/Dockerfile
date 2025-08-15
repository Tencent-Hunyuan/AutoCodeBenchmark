# 基于新的2.0镜像构建
FROM mirrors.tencent.com/llm-sandbox/multi-language-sandbox:2.0
USER root

# 设置环境变量
ENV PATH="/home/sandbox/.cargo/bin:/opt/node-v16.13.1-linux-x64/bin:/opt/conda/bin:/usr/local/lib/nodejs/node/bin:/usr/local/go/bin:/root/.local/share/coursier/bin:/root/.sdkman/candidates/kotlin/current/bin:/root/.sdkman/candidates/kotlin/current/bin:${PATH}" \
    CONDA_DIR="/opt/conda" \
    SDKMAN_DIR="/root/.sdkman" \
    PYTHONUNBUFFERED=1

# 安装python依赖
RUN /opt/conda/bin/pip install gunicorn flask flask_cors clickhouse_driver beautifulsoup4 requests psutil PyYAML statsmodels Pillow scikit-learn lxml numpy scipy opencv-python pyarrow pandas pytest

RUN npm install -g ts-node typescript tsx

RUN rm -rf /data
WORKDIR /data
RUN mkdir -p /data/logs

# 复制应用文件
COPY src/sandbox.py /data
COPY src/log.py /data
COPY src/gunicorn_config.py /data
COPY src/executor.py /data
COPY src/code_splicer.py /data
COPY src/clickhouse_reporter.py /data
COPY src/code.py /data
COPY src/safe_subprocess.py /data
COPY src/exec_outcome.py /data
COPY src/env.py /data
COPY src/code_config.yaml /data/code_config.yaml
COPY conf/rust /data/conf/rust
COPY conf/vimrc /root/.vimrc
COPY conf/apt/sources.list /etc/apt/sources.list
COPY conf/typescript/tsconfig.json /data/conf/typescript/tsconfig.json
COPY conf/typescript/package.json /data/conf/typescript/package.json
COPY conf/sandbox.bashrc /home/sandbox/.bashrc
COPY conf/sandbox.bash_profile /home/sandbox/.bash_profile
COPY conf/environment /etc/environment
COPY conf/dotnet/NuGet.Config /root/.nuget/NuGet/NuGet.Config
COPY data/dotnet /data/dotnet
COPY data/.nuget /root/.nuget
RUN cp -r /root/.nuget /home/sandbox && \
    # Ubuntu 20.04 及以后useradd 创建用户家目录时，默认权限变成 750，需要设置为755
    chmod -R 755 /home/sandbox && \
    chmod -R 755 /root/.sdkman /root/.local /home/sandbox/.cache /home/sandbox/.nuget 2>/dev/null || true && \
    chmod 755 /root && \
    # 设置sandbox用户家目录的所有权, 设置为root是为了防止sandbox用户删除家目录下的文件
    chown -R root:root /home/sandbox
# 设置执行权限
COPY docker-entrypoint.sh /data
RUN chmod +x /data/docker-entrypoint.sh

# 启动入口
ENTRYPOINT ["./docker-entrypoint.sh"]