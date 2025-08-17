#!/bin/bash

# 脚本出错时立即退出
set -e
# 将未设置的变量视为错误
set -u
# 管道中的任何命令失败都视为整个管道失败
set -o pipefail

# --- 配置区域 ---
LOCAL_ENV_FILE=".env"                 
# 本地环境文件名 (存储服务器访问凭证)
SERVER_ENV_FILE=".env.server"         
# 服务器端环境文件名 (将被复制到服务器并重命名为 .env)
FRONTEND_DIR="newsweb"              
# 前端项目目录名
FRONTEND_BUILD_DIR="dist"           
# 前端构建输出目录名 (检查你的项目，可能是 dist 或 build)
BACKEND_DIR="ChatBackend"           
# 后端项目目录名
COMPOSE_FILE="docker-compose.prod.yml"   
# Docker Compose 文件名
DEPLOY_SCRIPT_NAME=$(basename "$0") 
# 本脚本的文件名 (用于排除自身)

# --- 加载本地环境变量 (用于服务器访问) ---
echo ">>> 正在加载本地环境变量..."
if [ ! -f "$LOCAL_ENV_FILE" ]; then
    echo "错误: 本地环境文件 '$LOCAL_ENV_FILE' 未找到。"
    echo "请创建该文件并包含 SERVER_IP, SERVER_USER, 以及 SSH_KEY_PATH 或 SERVER_PASSWORD。"
    exit 1
fi

# 更安全地从 .env 文件导入变量，只处理 KEY=VALUE 格式
# 跳过空行和注释行，并处理可能的值中的空格
while IFS= read -r line || [[ -n "$line" ]]; do
    # 移除行首尾的空格
    cleaned_line=$(echo "$line" | sed 's/^[[:space:]]*//;s/[[:space:]]*$//')
    # 跳过空行和注释行
    if [[ -z "$cleaned_line" || "$cleaned_line" =~ ^# ]]; then
        continue
    fi
    # 检查是否为 KEY=VALUE 格式 (允许值为空)
    if [[ "$cleaned_line" =~ ^[a-zA-Z_][a-zA-Z0-9_]*=.* ]]; then
        # 分离 KEY 和 VALUE
        key=$(echo "$cleaned_line" | cut -d '=' -f 1)
        value=$(echo "$cleaned_line" | cut -d '=' -f 2-) # 获取第一个 '=' 后面的所有内容

        # 移除 VALUE 两端的引号 (单引号或双引号)
        # 注意：这只处理简单的两端引号，不处理值内部的引号
        cleaned_value=$(echo "$value" | sed -e "s/^'//" -e "s/'$//" -e 's/^"//' -e 's/"$//')
        
        # 导出清理后的 KEY=VALUE
        export "$key=$cleaned_value"
    else
        # 如果行不是 KEY=VALUE 格式，则打印警告到标准错误输出
        echo "警告: 跳过 $LOCAL_ENV_FILE 中的无效行: $cleaned_line" >&2
    fi
done < "$LOCAL_ENV_FILE"

# 检查必需的变量是否已设置
if [ -z "${SERVER_IP-}" ] || [ -z "${SERVER_USER-}" ] || [ -z "${REMOTE_DEPLOY_PATH-}" ]; then
  echo "错误: 必须在 $LOCAL_ENV_FILE 文件中设置 SERVER_IP, SERVER_USER, 和 REMOTE_DEPLOY_PATH"
  exit 1
fi
if [ -z "${SSH_KEY_PATH-}" ] && [ -z "${SERVER_PASSWORD-}" ]; then
  echo "错误: 必须在 $LOCAL_ENV_FILE 文件中设置 SSH_KEY_PATH 或 SERVER_PASSWORD"
  exit 1
fi
if [ ! -f "$SERVER_ENV_FILE" ]; then
    echo "错误: 服务器环境文件 '$SERVER_ENV_FILE' 未找到。"
    echo "请创建该文件并包含服务器运行所需的环境变量 (例如 SECRET_KEY, MONGO_URI 等)。"
    exit 1
fi


# --- 1. 本地构建前端应用 ---
echo ">>> 正在构建前端应用..."
cd "$FRONTEND_DIR"
# 确认使用正确的构建命令 (pnpm, npm, yarn)
echo "当前目录: $(pwd)"
echo "正在运行:  pnpm run build"
sudo npm run build
cd ..
echo "当前目录: $(pwd)"
echo ">>> 前端构建完成。"

# --- 2. 使用 rsync 将文件传输到服务器 ---
echo ">>> 正在传输文件到服务器 ($SERVER_USER@$SERVER_IP:$REMOTE_DEPLOY_PATH)..."

# rsync 命令的基本选项
# -a: 归档模式 (保留权限、时间戳等)
# -v: 详细模式
# -z: 压缩传输
# --delete: 删除目标目录中源目录没有的文件
RSYNC_OPTS="-avz --delete"

# SSH 连接选项 (优先使用 SSH 密钥)
SSH_CMD="ssh"
if [ -n "${SSH_KEY_PATH-}" ]; then
    # 使用 SSH 密钥
    if [ ! -f "$SSH_KEY_PATH" ]; then
        echo "错误: SSH 密钥文件未在 $SSH_KEY_PATH 找到"
        exit 1
    fi
    # 配置 rsync 使用指定的密钥文件 (使用单引号修正)
    RSYNC_OPTS="$RSYNC_OPTS -e 'ssh -i $SSH_KEY_PATH'"
    # 配置 ssh 命令使用指定的密钥文件
    SSH_CMD="ssh -i $SSH_KEY_PATH"
    echo "正在使用 SSH 密钥: $SSH_KEY_PATH"
elif [ -n "${SERVER_PASSWORD-}" ]; then
    # 使用密码 (安全性较低，可能需要交互式输入或安装 sshpass)
    echo "警告: 正在使用密码认证。推荐使用 SSH 密钥。"
    # 如果需要非交互式密码认证，可以安装 sshpass 并取消下面这行的注释
    # export SSHPASS="$SERVER_PASSWORD"; RSYNC_OPTS="$RSYNC_OPTS -e sshpass"; SSH_CMD="sshpass -p \"$SERVER_PASSWORD\" ssh"
fi

# 通过 SSH 在服务器上创建部署目录 (如果不存在)
echo ">>> 正在服务器上创建部署目录 (如果不存在)..."
$SSH_CMD "$SERVER_USER@$SERVER_IP" "mkdir -p $REMOTE_DEPLOY_PATH"

# 定义需要同步的文件/目录以及排除项
# 排除 node_modules, .git, 本地 .env, 脚本自身等
echo ">>> 正在同步应用文件..."

# --- 替换原来的 rsync $RSYNC_OPTS ... 命令 --- 
if [ -n "${SSH_KEY_PATH-}" ]; then
    # 如果设置了 SSH 密钥路径，则在 rsync 命令中直接使用 -e 选项
    rsync -avz --delete -e "ssh -i $SSH_KEY_PATH" \
        --exclude='.git/' \
        --exclude='.vscode/' \
        --exclude='__pycache__/' \
        --exclude='*.pyc' \
        --exclude='.DS_Store' \
        --exclude="$LOCAL_ENV_FILE" \
        --exclude="$SERVER_ENV_FILE" \
        --exclude="$DEPLOY_SCRIPT_NAME" \
        --exclude="$FRONTEND_DIR/node_modules/" \
        --exclude="$FRONTEND_DIR/.pnp.cjs" \
        --exclude="$FRONTEND_DIR/.pnp.loader.mjs" \
        --exclude="$FRONTEND_DIR/src/" \
        --exclude="$FRONTEND_DIR/public/" \
        --exclude="$FRONTEND_DIR/config/" \
        --exclude="$FRONTEND_DIR/types/" \
        --exclude="$FRONTEND_DIR/mock/" \
        --exclude="$FRONTEND_DIR/tests/" \
        --exclude="$FRONTEND_DIR/tsconfig.json" \
        --exclude="$FRONTEND_DIR/pnpm-lock.yaml" \
        --exclude="$FRONTEND_DIR/package.json" \
        --exclude="$FRONTEND_DIR/jest.config.ts" \
        --exclude="$BACKEND_DIR/.venv/" \
        --exclude="$BACKEND_DIR/results/" \
        --exclude="$BACKEND_DIR/data/" \
        ./"$FRONTEND_DIR"/"$FRONTEND_BUILD_DIR" ./${BACKEND_DIR} ./${COMPOSE_FILE} ./nginx.conf \
        "$SERVER_USER@$SERVER_IP":"$REMOTE_DEPLOY_PATH/"
else
    # 如果没有设置 SSH 密钥路径 (例如使用密码或 SSH Agent)，则不使用 -e 选项
    rsync -avz --delete \
        --exclude='.git/' \
        --exclude='.vscode/' \
        --exclude='__pycache__/' \
        --exclude='*.pyc' \
        --exclude='.DS_Store' \
        --exclude="$LOCAL_ENV_FILE" \
        --exclude="$SERVER_ENV_FILE" \
        --exclude="$DEPLOY_SCRIPT_NAME" \
        --exclude="$FRONTEND_DIR/node_modules/" \
        --exclude="$FRONTEND_DIR/.pnp.cjs" \
        --exclude="$FRONTEND_DIR/.pnp.loader.mjs" \
        --exclude="$FRONTEND_DIR/src/" \
        --exclude="$FRONTEND_DIR/public/" \
        --exclude="$FRONTEND_DIR/config/" \
        --exclude="$FRONTEND_DIR/types/" \
        --exclude="$FRONTEND_DIR/mock/" \
        --exclude="$FRONTEND_DIR/tests/" \
        --exclude="$FRONTEND_DIR/tsconfig.json" \
        --exclude="$FRONTEND_DIR/pnpm-lock.yaml" \
        --exclude="$FRONTEND_DIR/package.json" \
        --exclude="$FRONTEND_DIR/jest.config.ts" \
        --exclude="$BACKEND_DIR/.venv/" \
        --exclude="$BACKEND_DIR/results/" \
        --exclude="$BACKEND_DIR/data/" \
        ./"$FRONTEND_DIR"/"$FRONTEND_BUILD_DIR" ./${BACKEND_DIR} ./${COMPOSE_FILE} ./nginx.conf \
        "$SERVER_USER@$SERVER_IP":"$REMOTE_DEPLOY_PATH/"
fi
# ---------------------------------------------

# 单独传输服务器端的 .env 文件，并在服务器上重命名为 .env
echo ">>> 正在同步服务器环境文件 (.env.server -> .env)..."

# --- 替换原来的 rsync $RSYNC_OPTS ... 命令 --- 
if [ -n "${SSH_KEY_PATH-}" ]; then
    # 如果设置了 SSH 密钥路径，则在 rsync 命令中直接使用 -e 选项
    rsync -avz --delete -e "ssh -i $SSH_KEY_PATH" "$SERVER_ENV_FILE" "$SERVER_USER@$SERVER_IP":"$REMOTE_DEPLOY_PATH/.env"
else
    # 如果没有设置 SSH 密钥路径，则不使用 -e 选项
    rsync -avz --delete "$SERVER_ENV_FILE" "$SERVER_USER@$SERVER_IP":"$REMOTE_DEPLOY_PATH/.env"
fi
# ---------------------------------------------

echo ">>> 文件传输完成。"


# --- 3. 通过 SSH 在服务器上执行部署命令 ---
echo ">>> 正在服务器上执行部署命令..."

# 使用 EOF (End Of File) 来执行多行远程命令
echo "-----> SSH into server and run deployment commands..."
if [ -n "${SSH_KEY_PATH-}" ]; then
  ssh -i "$SSH_KEY_PATH" "$SERVER_USER@$SERVER_IP" << EOF
    echo "Current directory on server: \$(pwd)"
    cd "$REMOTE_DEPLOY_PATH" || exit 1
    echo "Changed to directory: \$(pwd)"

    # Check if server environment file exists and copy it
    if [ -f "$SERVER_ENV_FILE" ]; then
        echo "-----> Copying server environment file to backend..."
        cp "$SERVER_ENV_FILE" "${BACKEND_DIR}/.env"
    else
        echo "Warning: Server environment file '$SERVER_ENV_FILE' not found."
    fi

    # Stop and remove existing containers (if any)
    echo "-----> Stopping and removing existing containers..."
    docker-compose -f docker-compose.prod.yml down

    # Pull latest images (optional, useful if images are hosted)
    echo "-----> Pulling latest images..."
    docker-compose -f docker-compose.prod.yml pull

    # Build and start services
    echo "-----> Building and starting services..."
    docker-compose -f docker-compose.prod.yml up --build -d

    # Clean up dangling Docker images
    echo "-----> Cleaning up dangling Docker images..."
    docker image prune -f

    echo "-----> Deployment finished successfully!"
EOF
else
  ssh "$SERVER_USER@$SERVER_IP" << EOF
    echo "Current directory on server: \$(pwd)"
    cd "$REMOTE_DEPLOY_PATH" || exit 1
    echo "Changed to directory: \$(pwd)"

    # Check if server environment file exists and copy it
    if [ -f "$SERVER_ENV_FILE" ]; then
        echo "-----> Copying server environment file to backend..."
        cp "$SERVER_ENV_FILE" "${BACKEND_DIR}/.env"
    else
        echo "Warning: Server environment file '$SERVER_ENV_FILE' not found."
    fi

    # Stop and remove existing containers (if any)
    echo "-----> Stopping and removing existing containers..."
    docker-compose -f docker-compose.prod.yml down

    # Pull latest images (optional, useful if images are hosted)
    echo "-----> Pulling latest images..."
    docker-compose -f docker-compose.prod.yml pull

    # Build and start services
    echo "-----> Building and starting services..."
    docker-compose -f docker-compose.prod.yml up --build -d

    # Clean up dangling Docker images
    echo "-----> Cleaning up dangling Docker images..."
    docker image prune -f

    echo "-----> Deployment finished successfully!"
EOF
fi

echo ">>> 部署到 $SERVER_IP 完成！"
echo ">>> 你可以通过以下命令在服务器上查看实时日志："
echo "ssh $SERVER_USER@$SERVER_IP 'cd $REMOTE_DEPLOY_PATH && '"