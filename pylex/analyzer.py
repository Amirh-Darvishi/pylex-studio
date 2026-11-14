"""تحلیل‌گرهای لغوی و نحوی مستقل برای کد پایتون."""
import ast
import io
import keyword
import tokenize
from dataclasses import dataclass

@dataclass
class TokenInfo:
    """اطلاعات یک توکن شامل نوع، مقدار و موقعیت."""
    token_type: str
    value: str
    line: int
    column: int

@dataclass
class AnalysisResult:
    """نتیجه تحلیل نحوی و اطلاعات خطا."""
    success: bool
    message: str
    details: str = ""
    line: int = None
    column: int = None

def lexical_analysis(source: str):
    """متن پایتون را به توکن‌های لغوی تبدیل می‌کند.

    Args:
        source: کد منبع پایتون.

    Returns:
        فهرست TokenInfo شامل نوع، مقدار، خط و ستون هر توکن.
    """
    result = []
    for item in tokenize.generate_tokens(io.StringIO(source).readline):
        if item.type in (tokenize.ENCODING, tokenize.ENDMARKER):
            continue
        name = tokenize.tok_name.get(item.type, str(item.type))
        if item.type == tokenize.NAME and keyword.iskeyword(item.string):
            name = "KEYWORD"
        result.append(TokenInfo(name, item.string, item.start[0], item.start[1]))
    return result

def syntax_analysis(source: str):
    """ساختار نحوی کد را با ast.parse بررسی می‌کند.

    Args:
        source: متن برنامه.

    Returns:
        AnalysisResult با وضعیت، پیام و محل خطای احتمالی.
    """
    try:
        tree = ast.parse(source)
        count = sum(1 for _ in ast.walk(tree))
        return AnalysisResult(True, "تحلیل نحوی موفق بود.", f"تعداد گره‌های AST: {count}")
    except SyntaxError as exc:
        return AnalysisResult(False, exc.msg or "خطای نحوی", "SyntaxError", exc.lineno, exc.offset)

def format_tokens(tokens):
    """توکن‌ها را برای نمایش در پنل تحلیل قالب‌بندی می‌کند."""
    lines = [f"{'نوع':<18} {'خط':>5} {'ستون':>7}  مقدار", "-" * 65]
    for token in tokens:
        value = token.value.replace("\\n", r"\n").replace("\\t", r"\t")
        lines.append(f"{token.token_type:<18} {token.line:>5} {token.column:>7}  {value}")
    return "\\n".join(lines) if tokens else "توکنی وجود ندارد."
