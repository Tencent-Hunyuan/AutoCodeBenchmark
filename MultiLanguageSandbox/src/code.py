import os
import shutil
import uuid
import yaml
import re
from pathlib import Path
from log import setup_logger
from env import SANDBOX_UID, SANDBOX_GID

# 创建日志记录器
logger = setup_logger()
current_dir = Path(__file__).parent


class CodeConfig:
    def __init__(self, config_path=f"{current_dir}/code_config.yaml"):
        self.code_config = self.load_config(config_path)
        self.source_code_dir = self.code_config["code_store"]["source_code_dir"]
        self.supported_languages = self.code_config["supported_languages"]
        self.language_convert = self.code_config["language_convert"]

    def load_config(self, config_path):
        try:
            with open(config_path, "r", encoding="utf-8") as f:
                config = yaml.safe_load(f)
            logger.info(f"成功加载配置文件: {config_path}")
        except Exception as e:
            logger.error(f"加载配置文件失败: {e}")
            # 使用默认配置
            config = {
                "code_store": {"source_code_dir": "/data/codes/"},
                "supported_languages": {},
                "language_convert": {},
            }
        return config

    def get_language_config(self, language):
        language = self.language_convert.get(language.lower(), language.lower())
        if language not in self.supported_languages:
            raise ValueError(f"不支持的语言: {language}")
        language_config = self.supported_languages[language]
        language_config["lang"] = language
        language_config["source_code_dir"] = f"{self.source_code_dir}/{language}"
        return language_config

class SyntaxChecker:
    def __init__(self):
        pass

    def check(self, code, language):
        if language == "php":
            return self.check_php(code)
        return True

    def check_php(self, code):
        php_tag = re.findall(r"<\?php", code)
        if len(php_tag) != 1:
            return False
        code_lines = code.split("\n")
        if not re.match(r"^<\?php\s*$", code_lines[0]):
            return False
        if code_lines[-1] == "":
            tail_line = code_lines[-2]
        else:
            tail_line = code_lines[-1]
        if not re.match(r"^\s*\?>$", tail_line):
            return False
        return True

class CodeStore:
    def __init__(self):
        self.code_config = CodeConfig()
        self.syntax_checker = SyntaxChecker()

    def get_code_config(self):
        return self.code_config

    def change_ownership(self, directory="."):
        try:
            # 改变目录本身的所有权
            os.chown(directory, SANDBOX_UID, SANDBOX_GID)

            # 递归遍历目录下的所有文件和子目录
            for root, dirs, files in os.walk(directory):
                # 改变当前目录的所有权
                os.chown(root, SANDBOX_UID, SANDBOX_GID)

                # 改变所有文件的所有权
                for file in files:
                    file_path = os.path.join(root, file)
                    try:
                        os.chown(file_path, SANDBOX_UID, SANDBOX_GID)
                        logger.debug(f"已改变文件所有权: {file_path}")
                    except Exception as e:
                        logger.warning(f"无法改变文件所有权 {file_path}: {e}")

                # 改变所有子目录的所有权
                for dir_name in dirs:
                    dir_path = os.path.join(root, dir_name)
                    try:
                        os.chown(dir_path, SANDBOX_UID, SANDBOX_GID)
                        logger.debug(f"已改变目录所有权: {dir_path}")
                    except Exception as e:
                        logger.warning(f"无法改变目录所有权 {dir_path}: {e}")

            logger.debug(f"完成将目录 {directory} 下所有文件和目录所有权改为sandbox用户")

        except Exception as e:
            logger.error(f"改变所有权失败: {e}")
            raise

    def _perform_special_setup(self, language):
        """执行特殊设置"""
        language_config = self.code_config.get_language_config(language)
        special_setup = language_config.get("special_setup", [])
        for setup in special_setup:
            for action, path in setup.items():
                if action == "mkdir_if_not_exists":
                    if not os.path.exists(path):
                        os.makedirs(path)
                elif action == "change_ownership":
                    self.change_ownership(path)

    def build_code_env(self, request_data):
        language = request_data["lang"]
        source_code = request_data["source_code"]
        language_config = self.code_config.get_language_config(language).copy()
        language_config["src_uid"] = request_data["src_uid"]
        # 处理go语言的特殊设置
        if language_config["lang"] == "go":
            if "request_extensions" in request_data and "go_test_method" in request_data["request_extensions"]:
                language_config["go_test_method"] = request_data["request_extensions"]["go_test_method"]
                if language_config["go_test_method"] not in ["test", "main"]:
                    raise ValueError(f"不支持的go测试方法: {language_config['go_test_method']}, 只支持test和main")
            else:
                language_config["go_test_method"] = "test"

        code_dir = f"{language_config['source_code_dir']}/{uuid.uuid4().hex}"
        if not os.path.exists(code_dir):
            os.makedirs(code_dir)

        # 创建初始代码文件
        code_path = f"{code_dir}/{language_config['file_name_template']}"
        with open(code_path, "w") as f:
            f.write(source_code)

        need_syntax_check = language_config.get("syntax_check", False)
        if need_syntax_check and not self.syntax_checker.check(source_code, language_config["lang"]):
            language_config["syntax_error"] = True
            return language_config

        # 执行特殊设置
        self._perform_special_setup(language_config["lang"])

        # 处理特殊的handler环境设置
        if "handler" in language_config:
            logger.info(
                f"检测到特殊handler: {language_config['handler']}, 开始设置环境"
            )

            if language_config["handler"] == "dotnet_handler":
                # 设置.NET环境
                project_name = language_config.get("project_name", "MyProject")
                template_path = f"/data/dotnet/{language_config['lang']}/{project_name}"
                project_path = os.path.join(code_dir, project_name)
                shutil.copytree(template_path, project_path)

                # 复制源文件到项目中
                target_file = os.path.join(
                    project_path,
                    language_config.get(
                        "file_name_template",
                        "Program" + language_config["file_extension"],
                    ),
                )
                shutil.copy(code_path, target_file)
                self.change_ownership(project_path)

                # 更新语言配置信息，添加项目路径
                language_config["project_path"] = project_path
                language_config["code_path"] = target_file
                logger.info(f"创建{language_config['lang']}项目成功: {project_path}")

            elif language_config["handler"] == "rust_handler":
                # 设置Rust环境
                src_dir = os.path.join(code_dir, "src")
                os.makedirs(src_dir, exist_ok=True)

                # 复制配置文件
                shutil.copy("/data/conf/rust/Cargo.toml", code_dir)
                shutil.copy("/data/conf/rust/Cargo.lock", code_dir)

                # 复制源文件到src目录
                target_file = os.path.join(
                    src_dir, language_config.get("file_name_template", "main.rs")
                )
                shutil.copy(code_path, target_file)
                self.change_ownership(code_dir)

                # 更新语言配置信息
                language_config["project_path"] = code_dir
                language_config["code_path"] = target_file
                logger.info(f"创建Rust项目成功: {code_dir}")

            elif language_config["handler"] == "erlang_handler":
                # 设置Erlang环境，分析模块名
                with open(code_path, "r") as f:
                    code_content = f.read()
                    match = re.search(r"-module\((.*?)\)", code_content)
                    if match:
                        module_name = match.group(1)
                    else:
                        module_name = os.path.splitext(os.path.basename(code_path))[0]

                # 重命名文件为模块名
                erlang_file = os.path.join(code_dir, f"{module_name}.erl")
                shutil.copy(code_path, erlang_file)

                # 更新语言配置信息
                language_config["code_path"] = erlang_file
                language_config["module_name"] = module_name
                logger.info(f"创建Erlang环境成功: {erlang_file}, 模块名: {module_name}")

            elif language_config["handler"] == "go_handler":
                if language_config["go_test_method"] == "test":
                    go_test_file = os.path.join(code_dir, "main_test.go")
                    shutil.move(code_path, go_test_file)
                    language_config["code_path"] = go_test_file
                else:
                    language_config["code_path"] = code_path
                logger.info(f"创建Go测试环境成功: {language_config['code_path']}")
            
            elif language_config["handler"] == "java_handler":
                java_file = os.path.join(code_dir, "test.java")
                shutil.move(code_path, java_file)
                language_config["code_path"] = java_file
                logger.info(f"创建Java测试环境成功: {language_config['code_path']}")

        else:
            # 对于没有特殊handler的语言，使用原始路径
            language_config["code_path"] = code_path

        # 统一设置目录权限
        self.change_ownership(code_dir)
        logger.info(f"src_uid: {language_config['src_uid']}, 代码环境构建完成: {code_dir}")
        return language_config

    def destroy_code_env(self, language_config):
        code_dir = os.path.dirname(language_config["code_path"])
        shutil.rmtree(code_dir, ignore_errors=True)


if __name__ == "__main__":
    code_store = CodeStore()
    print(code_store.get_code_config().get_language_config("php"))
 # type: ignore