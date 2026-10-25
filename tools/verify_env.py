"""学生环境自检：python / 依赖 / git / 网络。

用法：python tools/verify_env.py
"""

from __future__ import annotations

import importlib
import shutil
import subprocess
import sys
from pathlib import Path

OK, BAD = "✓", "✗"


def check_python() -> bool:
    v = sys.version_info
    ok = (v.major, v.minor) >= (3, 11)
    print(f"{OK if ok else BAD} Python {v.major}.{v.minor}.{v.micro}（要求 ≥ 3.11）")
    return ok


def check_pkg(name: str, attr: str = "__version__", minimum: str = "") -> bool:
    try:
        mod = importlib.import_module(name)
        ver = getattr(mod, attr, "?")
        if name == "numpy" and str(ver).startswith("2."):
            print(f"{BAD} numpy {ver}（必须 < 2，否则部分 CPU 会 Illegal instruction）")
            return False
        print(f"{OK} {name} {ver}")
        return True
    except Exception:
        print(f"{BAD} 缺少依赖：{name}（pip install -r tools/requirements-course.txt）")
        return False


def check_git() -> bool:
    if not shutil.which("git"):
        print(f"{BAD} 未找到 git")
        return False
    name = subprocess.run(["git", "config", "user.name"], capture_output=True, text=True).stdout.strip()
    mail = subprocess.run(["git", "config", "user.email"], capture_output=True, text=True).stdout.strip()
    ok = bool(name and mail)
    print(f"{OK if ok else BAD} git 用户：{name or '(未设置)'} <{mail or '(未设置)'}>")
    return ok


def main() -> None:
    print("== 环境自检 ==")
    results = [check_python()]
    for pkg in ("litestar", "granian", "msgspec", "numpy", "pymysql", "pytest", "httpx"):
        results.append(check_pkg(pkg))
    results.append(check_git())

    course = Path(__file__).resolve().parent.parent
    for rel in ("01_课程标准.md", "slides/pptx", "09_项目任务书"):
        ok = (course / rel).exists()
        print(f"{OK if ok else BAD} {rel}")
        results.append(ok)

    print()
    if all(results):
        print("环境就绪，可以开始第 01 讲。")
    else:
        print("有项目未通过，按提示修复后重跑。")
        sys.exit(1)


if __name__ == "__main__":
    main()
