#!/usr/bin/env python3

import re
import sys
import json
import requests
from typing import Dict, Any, Generator, List, Callable, Set, Tuple
from log import setup_logger
from code import CodeConfig

# 创建日志记录器
logger = setup_logger("splice", "splice.log")


class CodeSplicer:
    def __init__(self):
        # 语言映射，同一种语言的不同叫法统一
        self.code_config = CodeConfig()

        # 映射语言到对应的处理函数
        self.lang_handlers = {
            "php": self.splice_php_code,
            "racket": self.splice_racket_code,
            "scheme": self.splice_scheme_code,
            "tcl": self.splice_tcl_code,
            "vb": self.splice_vb_code,
            "powershell": self.splice_powershell_code,
            "c#": self.splice_csharp_code,
            "dart": self.splice_dart_code,
            "kotlin": self.splice_kotlin_code,
            "javascript": self.splice_javascript_code,
            "go": self.splice_go_code,
            "cpp": self.splice_cpp_code,
            "java": self.splice_java_code,
            "haskell": self.splice_haskell_code,
            "common lisp": self.splice_lisp_code,
            "lua": self.splice_lua_code,
            "erlang": self.splice_erlang_code,
            'swift': self.splice_swift_code,
            # "rust": self.splice_rust_code, # rust语言中重复use只会报warning错误，不影响实际执行
            "default": self.splice_code_default
        }

    def splice_swift_code(self, code: str, assertions: str) -> str:
        # 定义需要检查的数学函数
        math_functions = ['pow', 'sin', 'exp', 'cos', 'sqrt', 'NSDictionary', 'NSDecimalSquareRoot']
        
        # 检查代码中是否使用了这些函数
        needs_imports = any(func in code for func in math_functions)
        has_foundation = 'import Foundation' in code
        has_glibc = 'import Glibc' in code
        
        # 如果需要导入，则在代码开头添加导入语句
        if needs_imports:
            imports = ""
            if not has_foundation:
                imports += "import Foundation\n"
            if not has_glibc:
                imports += "import Glibc\n"
            code = imports + "\n" + code
        
        # 将断言添加到代码末尾
        code += "\n" + assertions
        
        return code

    def splice_erlang_code(self, code: str, assertions: str) -> str:
        """
        合并Erlang代码和断言，自动导出测试函数
        """
        # 1. 找到所有 assertion 里的测试函数名（形如 test_xxx()）
        test_funs = re.findall(r'^\s*([a-zA-Z0-9_]+)\s*\(', assertions, re.MULTILINE)

        test_funs = list(set(test_funs))
        # 生成形如 test_sum_of_digits/0
        test_exports = [f"{name}/0" for name in test_funs]

        # 2. 查找-export([...])这一行
        export_pattern = r"^-export\s*\(\s*\[([^\]]*)\]\s*\)\."
        m = re.search(export_pattern, code, re.MULTILINE)
        if m:
            # 已有-export，合并
            existing_exports = [e.strip() for e in m.group(1).split(',') if e.strip()]
            # 合并并去重
            all_exports = list(dict.fromkeys(existing_exports + test_exports))
            new_export_line = f"-export([{', '.join(all_exports)}])."
            # 替换原有-export行
            merged_code = re.sub(export_pattern, new_export_line, code, count=1, flags=re.MULTILINE)
        else:
            # 没有-export，插入到-module之后
            module_pattern = r"^-module\s*\(\s*([^)]+)\s*\)\."
            m = re.search(module_pattern, code, re.MULTILINE)
            if not m:
                raise ValueError("代码缺少-module定义")
            insert_pos = m.end()
            new_export_line = f"\n-export([{', '.join(test_exports)}])."
            merged_code = code[:insert_pos] + new_export_line + code[insert_pos:]

        # 3. 合并代码和断言
        merged_result = merged_code.rstrip() + "\n\n" + assertions.lstrip()
        return merged_result

    def splice_haskell_code(self, code: str, assertions: str) -> str:
        # 收集所有 import 语句
        import_lines = set()
        code_body = []
        test_body = []

        # 处理 code_part
        for line in code.strip().splitlines():
            if line.strip().startswith('import '):
                import_lines.add(line.strip())
            else:
                code_body.append(line)

        # 处理 test_part
        for line in assertions.strip().splitlines():
            if line.strip().startswith('import '):
                import_lines.add(line.strip())
            else:
                test_body.append(line)

        # 拼接
        result = []
        if import_lines:
            result.extend(sorted(import_lines))
            result.append('')  # 空行

        result.extend(code_body)
        result.append('')  # 空行
        result.extend(test_body)

        return '\n'.join(result)

    def fix_lua_function_returns(self, code: str) -> str:
        # 找到主函数定义
        func_match = re.search(r'(local\s+function\s+\w+\s*\([^\)]*\)\s*)([\s\S]*?)(\nend)', code)
        if not func_match:
            return code  # 没找到函数直接返回

        func_head, func_body, func_end = func_match.groups()
        lines = func_body.split('\n')

        # 追踪 function/end，0表示最外层
        level = 0
        last_top_return_idx = -1
        for idx, line in enumerate(lines):
            # 检查 function 和 end，注意 function/end 可能在一行有注释
            if re.search(r'\bfunction\b', line):
                level += 1
            if re.search(r'\bend\b', line):
                level -= 1
            # 只在最外层找 return
            if level == 0 and re.match(r'^\s*return\b', line):
                last_top_return_idx = idx

        # 判断能否安全删除
        if last_top_return_idx != -1:
            ret_line = lines[last_top_return_idx].strip()
            # 只删掉 return res/return true/return false/return 0/return 1 这类，不删 return self/return {...}/return setmetatable
            if re.match(r'^return\s+(res|true|false|0|1|[a-zA-Z_][a-zA-Z0-9_]*)\s*$', ret_line):
                # 如果是 return self 或 return { 开头，不删
                if not re.match(r'^return\s+self\s*$', ret_line) and not re.match(r'^return\s*\{', ret_line):
                    lines[last_top_return_idx] = ''

        fixed_body = '\n'.join(lines)
        return func_head + fixed_body + func_end

    def fix_lua_module_return(self, code: str) -> str:
        # 如果已经有 InventoryManagement = ...，就不用再加
        if re.search(r'\bInventoryManagement\s*=', code):
            return code
        # 如果有 return { new = ... }，替换
        m = re.search(r'return\s*\{\s*new\s*=\s*([a-zA-Z_][a-zA-Z0-9_]*)\s*\}\s*$', code)
        if m:
            func_name = m.group(1)
            code = re.sub(r'return\s*\{\s*new\s*=\s*([a-zA-Z_][a-zA-Z0-9_]*)\s*\}\s*$', f'InventoryManagement = {{ new = {func_name} }}', code)
            return code
        # 否则，检测有没有 new_inventory_management 定义，有则加
        if re.search(r'local\s+function\s+new_inventory_management\s*\(', code):
            code += "\n\nInventoryManagement = { new = new_inventory_management }"
        return code

    def splice_lua_code(self, code: str, assertions: str) -> str:
        # 修正实现代码的 return 问题
        impl_code = self.fix_lua_function_returns(code)
        impl_code = self.fix_lua_module_return(impl_code)

        # 获取实现函数名
        func_name_match = re.search(r'local\s+function\s+(\w+)\s*\(', impl_code)
        if not func_name_match:
            raise ValueError("实现代码未检测到函数定义")
        impl_func_name = func_name_match.group(1)

        # 检查测试用例是否用 table 方式调用
        table_call_match = re.search(r'(\w+)\.' + re.escape(impl_func_name) + r'\s*\(', assertions)
        if table_call_match:
            table_name = table_call_match.group(1)
            # 自动加上 table 包装
            impl_code += f"\n\n{table_name} = {{ {impl_func_name} = {impl_func_name} }}"
        # 2. 检查直接调用的函数名（如 shortest_subarray(xxx)）
        # 捕获 assert(函数名(
        direct_call_matches = re.findall(r'assert\((\w+)\s*\(', assertions)
        if direct_call_matches:
            # 取第一个出现的
            test_func_name = direct_call_matches[0]
            # 如果测试用例调用名和实现名不一致，自动加别名
            if test_func_name != impl_func_name:
                impl_code += f"\n\n{test_func_name} = {impl_func_name}"

        # 去掉测试代码中的 require 和多余导入
        test_lines = [line for line in assertions.splitlines() if not re.match(r'^\s*local\s+\w+\s*=\s*require\b', line)]
        assertions = '\n'.join(test_lines)
        return impl_code.strip() + '\n\n' + assertions.strip()

    def splice_scheme_code(self, code: str, assertions: str) -> str:
        # 提取 module 名称
        m = re.search(r'\(module\s+([^\s]+)\s+racket', code)
        if not m:
            raise ValueError("No module name found!")
        module_name = m.group(1)

        # 确保 module 括号闭合
        left = code.count('(')
        right = code.count(')')
        if left > right:
            code += ')' * (left - right)

        # 去掉 code 里的 require
        code = re.sub(r"\(require\s+'[^\)]+\)", '', code)
        code = re.sub(r"\(require\s+rackunit\)", '', code)
        code = re.sub(r"\(require\s+\(submod\s+\.\s+[^\)]+\)\)", '', code)

        # 去掉 assertions 里的 #lang racket 和 require
        assertions = re.sub(r'#lang\s+racket\s*', '', assertions)
        assertions = re.sub(r"\(require\s+'[^\)]+\)", '', assertions)
        assertions = re.sub(r"\(require\s+rackunit\)", '', assertions)
        assertions = re.sub(r"\(require\s+\(submod\s+\.\s+[^\)]+\)\)", '', assertions)

        # 插入 require (submod "." module_name)
        merged = (
            code.strip() + '\n\n'
            + '(require rackunit)\n'
            + f'(require (submod "." {module_name}))\n\n'
            + assertions.strip() + '\n'
        )
        return merged

    def remove_lang(self, s: str) -> List[str]:
        lines = s.splitlines()
        return [line for line in lines if not line.strip().startswith("#lang")]

    def splice_racket_code(self, code: str, assertions: str) -> str:
        # 获取第一个 #lang 行
        for line in code.splitlines():
            if line.strip().startswith("#lang"):
                lang_line = line.strip()
                break
        else:
            lang_line = "#lang racket"

        code_body = "\n".join(self.remove_lang(code)).rstrip()
        assertions_body = "\n".join(self.remove_lang(assertions)).rstrip()

        # 合并，确保中间有两个换行
        return f"{lang_line}\n\n{code_body}\n\n{assertions_body}\n"

    def process_lisp_code(self, code: str, assertions: str) -> Tuple[str, str, List[str]]:
        """处理 Lisp 代码的清理和标准化

        Args:
            code: 原始代码
            assertions: 断言代码

        Returns:
            tuple: (清理后的代码, 清理后的断言, 函数名列表)
        """
        # 1. 移除 in-package 语句
        code = re.sub(r'\(in-package[^\)]*\)', '', code, flags=re.IGNORECASE)

        # 2. 提取所有 defun
        defuns = []
        pattern = r'(\(defun\s+[^\)]+\)[\s\S]*?\))(?=\s*\(defun|\s*$)'
        matches = re.findall(pattern, code, re.IGNORECASE)
        for m in matches:
            defuns.append(m.strip())

        # 3. 提取函数名
        func_names = re.findall(r'\(defun\s+([^\s\(\)]+)', '\n'.join(defuns), re.IGNORECASE)

        # 4. 清理断言代码
        # 4.1 修正 use 列表
        assertions = re.sub(
            r'\(:use\s+([^\)]*\s)?(:[a-zA-Z0-9-]+\s*)+\)',
            '(:use :cl)',
            assertions,
            flags=re.IGNORECASE
        )

        # 4.2 移除 cl-user: 前缀
        for name in func_names:
            assertions = re.sub(rf'\bcl-user:{name}\b', name, assertions)

        return code, assertions, func_names

    def splice_lisp_code(self, code: str, assertions: str) -> str:
        # 清理代码
        code, assertions, func_names = self.process_lisp_code(code, assertions)

        # 找到 assertions 里 (in-package ...) 的位置
        lines = assertions.splitlines()
        insert_index = None
        for i, line in enumerate(lines):
            if line.strip().lower().startswith('(in-package'):
                insert_index = i + 1
                break
        if insert_index is None:
            raise ValueError('assertions 中未找到 (in-package ...) 语句')

        # 提取所有 defun
        defuns = []
        pattern = r'(\(defun\s+[^\)]+\)[\s\S]*?\))(?=\s*\(defun|\s*$)'
        matches = re.findall(pattern, code, re.IGNORECASE)
        for m in matches:
            defuns.append(m.strip())

        # 插入所有 defun 到 in-package 后
        new_lines = lines[:insert_index] + [''] + defuns + [''] + lines[insert_index:]
        return '\n'.join(new_lines)

    def splice_tcl_code(self, code: str, assertions: str) -> str:
        """
        合并TCL代码，处理shebang行

        Args:
            code: 主要代码
            assertions: 断言代码

        Returns:
            合并后的代码
        """
        lines = assertions.splitlines()
        # 检查首行是否是 shebang
        if lines and lines[0].strip() == "#!/usr/bin/env tclsh":
            lines = lines[1:]
        assertions_clean = "\n".join(lines)
        if not code.endswith('\n'):
            code += '\n'

        return code + assertions_clean

    def splice_vb_code(self, code: str, assertions: str) -> str:
        """
        合并VB代码，处理Imports和模块名冲突、主入口函数名替换
        """
        # 1. 收集Imports
        import_lines = set()
        code_body = []
        assertions_body = []

        for line in code.splitlines():
            if line.strip().lower().startswith('imports '):
                import_lines.add(line.strip())
            else:
                code_body.append(line)
        for line in assertions.splitlines():
            if line.strip().lower().startswith('imports '):
                import_lines.add(line.strip())
            else:
                assertions_body.append(line)

        # 2. 获取模块名
        def get_module_name(lines):
            for line in lines:
                m = re.match(r'^\s*Module\s+(\w+)', line, re.IGNORECASE)
                if m:
                    return m.group(1)
            return None

        code_module = get_module_name(code_body)
        assertions_module = get_module_name(assertions_body)

        # 3. 如果模块名冲突，重命名断言模块
        if code_module and assertions_module and code_module.lower() == assertions_module.lower():
            assertions_body = [
                re.sub(rf'\bModule\s+{assertions_module}\b', f'Module {assertions_module}Tests', l, flags=re.IGNORECASE)
                if re.match(r'^\s*Module\s+', l, re.IGNORECASE) else l
                for l in assertions_body
            ]

        # 4. 替换断言中的测试入口为Main
        func_name = None
        for line in assertions_body:
            m = re.match(r'.*\b(Sub|Function)\s+(\w+)\b', line, re.IGNORECASE)
            if m and not func_name:
                func_name = m.group(2)
                break
        if func_name and func_name.lower() != 'main':
            # 只替换声明和调用，不全局替换（避免误伤其他地方）
            new_assertions_body = []
            for l in assertions_body:
                # 替换Sub/Function声明
                l2 = re.sub(rf'(\b(Sub|Function)\s+){func_name}\b', r'\1Main', l)
                # 替换调用（如 Public Shared Sub RunTests 改为 Main）
                l2 = re.sub(rf'\b{func_name}\b', 'Main', l2) if re.match(r'^\s*(Public\s+)?(Shared\s+)?Sub\s+', l, re.IGNORECASE) else l2
                new_assertions_body.append(l2)
            assertions_body = new_assertions_body

        # 5. 合并输出
        result = '\n'.join(sorted(import_lines)) + '\n'
        result += '\n'.join(code_body) + '\n'
        result += '\n'.join(assertions_body) + '\n'
        return result

    def splice_powershell_code(self, code: str, assertions: str) -> str:
        """
        合并PowerShell代码，注释掉Write-Output行

        Args:
            code: 主要代码
            assertions: 断言代码

        Returns:
            合并后的代码
        """
        code_lines = [
            '# ' + line if re.match(r'^\s*Write-Output\b', line) else line
            for line in code.splitlines()
        ]
        return '\n'.join(code_lines + assertions.splitlines())

    def splice_php_code(self, code: str, assertions: str) -> str:
        """
        合并PHP代码，处理PHP标签

        Args:
            code: 主要代码
            assertions: 断言代码

        Returns:
            合并后的代码
        """
        # 去掉 code 里的所有 '?>'
        code = code.replace('?>', '')
        code = code.strip()
        if not code.startswith('<?php'):
            code = '<?php\n' + code
        # 去掉 assertions 里的所有 '<?php'
        assertions = assertions.replace('<?php', '')
        return code.strip() + '\n' + assertions.strip() + '\n'

    def splice_rust_code(self, code: str, assertions: str) -> str:
        """
        合并Rust代码，处理main函数和断言

        Args:
            code: 主要代码
            assertions: 断言代码

        Returns:
            合并后的代码
        """
        # 提取use语句的函数
        def extract_use_statements(text: str) -> set:
            use_statements = set()
            for line in text.split('\n'):
                # 只匹配行首的use语句（不允许前面有空白字符），必须以分号结尾
                match = re.match(r'^use\s+[^;]+;', line)
                if match:
                    use_statements.add(match.group().strip())
            return use_statements

        # 移除use语句的函数
        def remove_use_statements(text: str) -> list:
            lines = []
            for line in text.split('\n'):
                # 只移除行首的use语句，保留有缩进的use语句
                if not re.match(r'^use\s+[^;]+;', line):
                    lines.append(line)
            return lines

        # 1. 提取并合并use语句
        code_uses = extract_use_statements(code)
        assertions_uses = extract_use_statements(assertions)

        # 合并并去重，按字母顺序排序
        all_uses = sorted(code_uses.union(assertions_uses))

        # 2. 移除原有的use语句
        code_without_uses = remove_use_statements(code)
        assertions_without_uses = remove_use_statements(assertions)

        # 3. 构建最终代码
        result = []

        # 添加合并后的use语句
        if all_uses:
            result.extend(all_uses)
            result.append('')  # 空行分隔

        # 添加主要代码（去除use语句后）
        result.extend(code_without_uses)

        # 添加空行分隔
        if code_without_uses and assertions_without_uses:
            result.append('')

        # 添加断言代码（去除use语句后）
        result.extend(assertions_without_uses)

        return '\n'.join(result)

    def splice_code_default(self, code: str, assertions: str) -> str:
        """
        默认的代码合并方式，简单拼接

        Args:
            code: 主要代码
            assertions: 断言代码

        Returns:
            合并后的代码
        """
        return code + "\n" + assertions

    def merge_using_statements(self, code: str, assertions: str) -> str:
        """
        合并两个代码块中的 using 语句

        Args:
            code: 主要代码
            assertions: 断言代码

        Returns:
            合并using语句后的代码
        """
        # 提取所有 using 语句
        using_pattern = r'using\s+[^;]+;'
        code_usings = set(re.findall(using_pattern, code))
        assertions_usings = set(re.findall(using_pattern, assertions))

        # 合并并去重
        all_usings = sorted(code_usings.union(assertions_usings))
        using_block = '\n'.join(all_usings) + '\n\n' if all_usings else ''

        # 移除原始代码中的 using 语句
        code_without_usings = re.sub(using_pattern, '', code).strip()
        assertions_without_usings = re.sub(using_pattern, '', assertions).strip()

        return using_block + code_without_usings + '\n\n' + assertions_without_usings

    def extract_import_statements(self, lang: str, text: str) -> Set[str]:
        """
        从代码中提取import语句

        Args:
            text: 源代码文本

        Returns:
            import语句集合
        """
        import_statements = set()
        for line in text.split('\n'):
            # 对于 Kotlin，import 语句不需要分号结尾
            if lang.lower() == 'kotlin':
                match = re.match(r'^\s*import\s+[^;]+$', line)
            else:
                # 其他语言（如 Dart）需要分号结尾
                match = re.match(r'^\s*import\s+[^;]+;', line)
            if match:
                import_statements.add(match.group().strip())
        return import_statements

    def remove_import_statements(self, lang: str, text: str) -> str:
        """
        从代码中移除import语句

        Args:
            text: 源代码文本

        Returns:
            移除import语句后的代码
        """
        lines = []
        for line in text.split('\n'):
            # 对于 Kotlin，import 语句不需要分号结尾
            if lang.lower() == 'kotlin':
                if not re.match(r'^\s*import\s+[^;]+$', line):
                    lines.append(line)
            else:
                # 其他语言（如 Dart）需要分号结尾
                if not re.match(r'^\s*import\s+[^;]+;', line):
                    lines.append(line)
        return '\n'.join(lines).strip()

    def splice_csharp_code(self, code: str, assertions: str) -> str:
        """
        专门处理 C# 代码的拼接函数，包含三个步骤：
        1. 合并 using 语句（仅处理行首的 using 语句）
        2. 添加 public 关键字（仅对没有修饰符的 static 方法）
        3. 智能重命名 RunTests 为 Main（仅在没有现有 Main 入口函数时执行）

        Args:
            code: 主要代码
            assertions: 断言代码

        Returns:
            处理后的合并代码
        """
        # 1. 合并 using 语句
        # 按行处理，只匹配行首的 using 语句
        def extract_using_statements(text: str) -> set:
            using_statements = set()
            for line in text.split('\n'):
                # 匹配行首的 using 语句，允许前面有空白字符
                match = re.match(r'^\s*using\s+[^;]+;', line)
                if match:
                    using_statements.add(match.group().strip())
            return using_statements

        code_usings = extract_using_statements(code)
        assertions_usings = extract_using_statements(assertions)

        # 合并并去重
        all_usings = sorted(code_usings.union(assertions_usings))
        using_block = '\n'.join(all_usings) + '\n\n' if all_usings else ''

        # 移除原始代码中的 using 语句
        def remove_using_statements(text: str) -> str:
            lines = []
            for line in text.split('\n'):
                # 跳过行首的 using 语句
                if not re.match(r'^\s*using\s+[^;]+;', line):
                    lines.append(line)
            return '\n'.join(lines).strip()

        code_without_usings = remove_using_statements(code)
        assertions_without_usings = remove_using_statements(assertions)

        # 合并代码
        merged_code = using_block + code_without_usings + '\n\n' + assertions_without_usings

        # 2. 添加 public 关键字
        # 第一步：先移除所有已经带有修饰符的 static 方法行
        lines = merged_code.split('\n')
        filtered_lines = []
        for line in lines:
            # 跳过已经带有修饰符的行
            if re.search(r'^\s*(public|private|protected|internal)\s+static\b', line):
                filtered_lines.append(line)
                continue
            # 处理没有修饰符的 static 方法
            if re.search(r'^\s*static\b', line):
                # 在 static 前添加 public
                line = re.sub(r'^\s*static\b', '    public static', line)
            filtered_lines.append(line)

        merged_code = '\n'.join(filtered_lines)

        # 3. 智能重命名 RunTests 为 Main
        # 检查是否已经存在 Main 入口函数
        has_main_entry = bool(re.search(r'^\s*(public\s+)?static\s+void\s+Main\s*\(', merged_code, re.MULTILINE))

        # 只有在没有 Main 入口函数时才进行替换
        if not has_main_entry:
            # 检查是否存在 RunTests 函数定义
            has_run_tests = bool(re.search(r'^\s*(public\s+)?static\s+void\s+RunTests\s*\(', merged_code, re.MULTILINE))
            if has_run_tests:
                # 只替换函数定义，不替换函数调用
                # 因为 Main 函数作为入口函数，不应该被显式调用
                merged_code = re.sub(r'(\s*)(public\s+)?static\s+void\s+RunTests\s*\(', r'\1\2static void Main(', merged_code)

        return merged_code

    def splice_dart_code(self, code: str, assertions: str) -> str:
        """
        专门处理 Dart 代码的拼接函数，只处理 import 语句的合并

        Args:
            code: 主要代码
            assertions: 断言代码

        Returns:
            处理后的合并代码
        """
        # 1. 合并 import 语句
        code_imports = self.extract_import_statements(lang='dart', text=code)
        assertions_imports = self.extract_import_statements(lang='dart', text=assertions)

        # 合并并去重
        all_imports = sorted(code_imports.union(assertions_imports))
        import_block = '\n'.join(all_imports) + '\n\n' if all_imports else ''

        # 移除原始代码中的 import 语句
        code_without_imports = self.remove_import_statements(lang='dart', text=code)
        assertions_without_imports = self.remove_import_statements(lang='dart', text=assertions)

        # 合并代码
        return import_block + code_without_imports + '\n\n' + assertions_without_imports

    def splice_kotlin_code(self, code: str, assertions: str) -> str:
        """
        专门处理 Kotlin 代码的拼接函数，只处理 import 语句的合并

        Args:
            code: 主要代码
            assertions: 断言代码

        Returns:
            处理后的合并代码
        """
        # 1. 合并 import 语句
        code_imports = self.extract_import_statements(lang='kotlin', text=code)
        assertions_imports = self.extract_import_statements(lang='kotlin', text=assertions)

        # 合并并去重
        all_imports = sorted(code_imports.union(assertions_imports))
        import_block = '\n'.join(all_imports) + '\n\n' if all_imports else ''

        # 移除原始代码中的 import 语句
        code_without_imports = self.remove_import_statements(lang='kotlin', text=code)
        assertions_without_imports = self.remove_import_statements(lang='kotlin', text=assertions)

        # 合并代码
        return import_block + code_without_imports + '\n\n' + assertions_without_imports

    def splice_javascript_code(self, code: str, assertions: str) -> str:
        """
        专门处理 JavaScript 代码的拼接函数

        Args:
            code: 主要代码
            assertions: 断言代码

        Returns:
            处理后的合并代码
        """
        def has_function_definition(code: str, func_name: str) -> bool:
            """检查代码中是否定义了指定函数"""
            # 匹配函数定义：function funcName() 或 const funcName = function() 或 funcName = function()
            patterns = [
                rf'function\s+{re.escape(func_name)}\s*\(',
                rf'const\s+{re.escape(func_name)}\s*=\s*function\s*\(',
                rf'let\s+{re.escape(func_name)}\s*=\s*function\s*\(',
                rf'var\s+{re.escape(func_name)}\s*=\s*function\s*\(',
                rf'{re.escape(func_name)}\s*=\s*function\s*\(',
                rf'const\s+{re.escape(func_name)}\s*=\s*\(',  # 箭头函数
                rf'let\s+{re.escape(func_name)}\s*=\s*\(',
                rf'var\s+{re.escape(func_name)}\s*=\s*\(',
                rf'{re.escape(func_name)}\s*=\s*\('
            ]
            return any(re.search(pattern, code) for pattern in patterns)

        def has_entry_function_call(code: str, entry_func: str) -> bool:
            """检查代码中是否已经包含入口函数调用（在代码末尾的独立调用）"""
            # 检查是否在代码末尾有 \n\nfuncName() 的调用
            pattern = rf'\n\n{re.escape(entry_func)}\s*\(\s*\)\s*$'
            return bool(re.search(pattern, code))

        def safe_add_entry(code: str, entry_func: str) -> str:
            """安全地添加入口函数调用，避免重复"""
            if not has_entry_function_call(code, entry_func):
                return code + f"\n\n{entry_func}()"
            return code

        merged_code = code + "\n" + assertions

        # 检查是否定义了测试函数，如果定义了就添加对应的入口调用
        if has_function_definition(merged_code, "demoTesting"):
            return safe_add_entry(merged_code, "demoTesting")
        elif has_function_definition(merged_code, "fullTesting"):
            return safe_add_entry(merged_code, "fullTesting")
        else:
            # 如果都没有定义测试函数，说明测试代码本身就是完整的，直接返回
            return merged_code

    def _go_extract_and_merge_imports(self, code_blocks: list) -> str:
        """提取并合并Go代码中的import语句"""
        imports = set()
        for code in code_blocks:
            # 匹配带括号的多行import和单行import
            matches = re.findall(r'import\s*(?:\((.*?)\)|"([^"]+)")', code, re.DOTALL)
            for match in matches:
                # 处理两种匹配结果
                for imp in match:
                    if imp.strip():
                        # 分割多行import中的各个包
                        for line in imp.split('\n'):
                            line = line.strip()
                            if line and not line.startswith('//'):  # 忽略注释
                                # 去除可能的引号和分号
                                line = line.replace('"', '').replace(';', '').strip()
                                if line:
                                    imports.add(line)

        # 生成合并后的import语句
        if imports:
            merged_import = "import (\n"
            for imp in imports:
                merged_import += f'    "{imp}"\n'
            merged_import += ")"
        else:
            merged_import = ""

        return merged_import

    def _go_clean_package_imports(self, code: str) -> str:
        """清理Go代码中的package和import语句"""
        code = re.sub(r'import\s*(?:\(.*?\)|"[^"]+")\s*', '', code, flags=re.DOTALL)
        code = code.replace("package main", "")
        return code.strip()

    def _go_remove_unused_imports(self, go_code: str) -> str:
        """移除Go代码中未使用的import包"""
        # 1. 找出所有import语句（包括分组和独立import）
        imports = []

        # 处理分组import (import (...))
        for match in re.finditer(r'import\s*\(([\s\S]*?)\)', go_code):
            imports.append(('grouped', match.start(), match.end(), match.group(1)))

        # 处理独立import (import "pkg")
        for match in re.finditer(r'import\s+"([^"]+)"', go_code):
            imports.append(('single', match.start(), match.end(), match.group(1)))

        # 如果没有import语句，直接返回
        if not imports:
            return go_code

        # 2. 收集所有导入的包
        imported_pkgs = set()
        for imp_type, start, end, content in imports:
            if imp_type == 'grouped':
                # 从分组中提取所有包
                imported_pkgs.update(re.findall(r'"([^"]+)"', content))
            else:  # single
                imported_pkgs.add(content)

        # 3. 找出实际使用的包
        used_pkgs: Set[str] = set()
        for pkg in imported_pkgs:
            pkg_identifier = pkg.split('/')[-1]
            # 排除import部分检查使用情况
            code_without_imports = go_code
            for _, start, end, _ in imports:
                code_without_imports = code_without_imports[:start] + ' ' * (end - start) + code_without_imports[end:]
            pkg_identifier = re.escape(pkg_identifier)
            if re.search(rf'(?<!\w){pkg_identifier}(?!\w)', code_without_imports):
                used_pkgs.add(pkg)

        # 4. 重建代码
        result = []
        last_end = 0

        for imp_type, start, end, content in imports:
            # 添加import之前的代码
            result.append(go_code[last_end:start])

            if imp_type == 'grouped':
                # 重建分组import
                used_in_group = []
                for line in content.split('\n'):
                    line = line.strip()
                    if line:
                        pkg_match = re.search(r'"([^"]+)"', line)
                        if pkg_match and pkg_match.group(1) in used_pkgs:
                            used_in_group.append(line)

                if used_in_group:
                    result.append('import (\n')
                    for line in used_in_group:
                        result.append(f'    {line}\n')
                    result.append(')')
            else:  # single
                if content in used_pkgs:
                    result.append(f'import "{content}"')

            last_end = end

        # 添加剩余的代码
        result.append(go_code[last_end:])

        return ''.join(result)

    def splice_go_code(self, code: str, assertions: str) -> str:
        """
        专门处理 Go 代码的拼接函数

        Args:
            code: 主要代码
            assertions: 断言代码

        Returns:
            处理后的合并代码
        """
        # 提取和合并import
        import_info = self._go_extract_and_merge_imports([code, assertions])

        # 清理package和import
        clean_code = self._go_clean_package_imports(code)
        clean_assertions = self._go_clean_package_imports(assertions)

        # 重构代码
        merged_code = f"package main\n{import_info}\n\n{clean_code}\n\n{clean_assertions}"

        # 判断测试类型并添加main函数
        if not re.search(r'func\s+Test\w+', assertions):
            # 检查是否已经有main函数
            if not re.search(r'func\s+main\s*\(', merged_code):
                # 检查是否定义了demoTesting或fullTesting函数
                demo_testing_defined = re.search(r'func\s+demoTesting\s*\(', merged_code)
                full_testing_defined = re.search(r'func\s+fullTesting\s*\(', merged_code)

                if demo_testing_defined:
                    merged_code += "\n\nfunc main() {demoTesting()}"
                elif full_testing_defined:
                    merged_code += "\n\nfunc main() {fullTesting()}"

        return self._go_remove_unused_imports(merged_code)

    def splice_cpp_code(self, code: str, assertions: str) -> str:
        """
        专门处理 C++ 代码的拼接函数

        Args:
            code: 主要代码
            assertions: 断言代码

        Returns:
            处理后的合并代码
        """
        # 提取主函数之前的部分作为模型函数
        model_func = code.strip().split("int main")[0]
        merged_code = model_func + "\n" + assertions
        return "#include <iostream>\nusing namespace std;\n" + merged_code

    def splice_java_code(self, code: str, assertions: str) -> str:
        """
        专门处理 Java 代码的拼接函数

        Args:
            code: 主要代码
            assertions: 断言代码

        Returns:
            处理后的合并代码
        """
        # 将主函数中的public class，private class 和 protected class都转成class
        main_code = code.replace("public class", "class").replace("private class", "class").replace("protected class", "class")

        # 提取用到的包
        answer_packages = [line for line in main_code.split('\n') if line.startswith("import ")]

        # 将package开头的行以及导入包的行去除
        answer_code = [line for line in main_code.split('\n') if not (line.startswith("import ") or line.startswith("package "))]
        answer_code = "\n".join(answer_code)

        # 提取测试函数的用到的包
        test_packages = [line for line in assertions.split('\n') if line.startswith("import ")]

        # 对导入的包去重
        all_packages = answer_packages + test_packages
        all_packages = list(set(all_packages))
        all_packages = "\n".join(all_packages)

        # 将package开头的行以及导入包的行去除
        test_code = [line for line in assertions.split('\n') if not (line.startswith("import ") or line.startswith("package "))]
        test_code = "\n".join(test_code)

        # 拼接
        return all_packages + "\n" + answer_code + "\n" + test_code

    def splice_code(self, lang: str, code: str, assertions: str) -> Dict[str, str]:
        """
        根据语言类型合并代码和断言

        Returns:
            包含spliced_code字段的字典
        """
        universal_lang = self.code_config.get_language_config(lang)["lang"]
        # 使用字典映射获取对应的处理器
        handler = self.lang_handlers.get(universal_lang, self.lang_handlers["default"])

        if universal_lang not in self.lang_handlers:
            logger.warning(f"未找到 {universal_lang} 的专用处理器，使用默认合并方式")
        else:
            logger.info(f"使用 {universal_lang} 的专用处理器进行合并")

        spliced_code = handler(code, assertions)

        return {"spliced_code": spliced_code}
