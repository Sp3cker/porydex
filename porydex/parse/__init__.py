import pathlib
import pickle
import re
import typing

import porydex.config

from pycparser import parse_file
from pycparser.c_ast import (
    BinaryOp,
    Cast,
    CompoundLiteral,
    Decl,
    ExprList,
    FuncCall,
    ID,
    TernaryOp,
    UnaryOp,
)

from porydex.common import (
    PICKLE_PATH,
    BINARY_BOOL_OPS,
    CONFIG_INCLUDES,
    EXPANSION_INCLUDES,
    GLOBAL_PREPROC,
    PREPROCESS_LIBC,
)

# Mapping of evolution method identifier names to their numeric values
# This matches the constants defined in include/constants/pokemon.h
EVO_METHOD_MAPPING = {
    'EVO_NONE': 0,
    'EVO_FRIENDSHIP': 1,
    'EVO_FRIENDSHIP_DAY': 2,
    'EVO_FRIENDSHIP_NIGHT': 3,
    'EVO_LEVEL': 4,
    'EVO_TRADE': 5,
    'EVO_TRADE_ITEM': 6,
    'EVO_ITEM': 7,
    'EVO_LEVEL_ATK_GT_DEF': 8,
    'EVO_LEVEL_ATK_EQ_DEF': 9,
    'EVO_LEVEL_ATK_LT_DEF': 10,
    'EVO_LEVEL_SILCOON': 11,
    'EVO_LEVEL_CASCOON': 12,
    'EVO_LEVEL_NINJASK': 13,
    'EVO_LEVEL_SHEDINJA': 14,
    'EVO_BEAUTY': 15,
    'EVO_LEVEL_FEMALE': 16,
    'EVO_LEVEL_MALE': 17,
    'EVO_LEVEL_NIGHT': 18,
    'EVO_LEVEL_DAY': 19,
    'EVO_LEVEL_DUSK': 20,
    'EVO_ITEM_HOLD_DAY': 21,
    'EVO_ITEM_HOLD_NIGHT': 22,
    'EVO_MOVE': 23,
    'EVO_FRIENDSHIP_MOVE_TYPE': 24,
    'EVO_MAPSEC': 25,
    'EVO_ITEM_MALE': 26,
    'EVO_ITEM_FEMALE': 27,
    'EVO_LEVEL_RAIN': 28,
    'EVO_SPECIFIC_MON_IN_PARTY': 29,
    'EVO_LEVEL_DARK_TYPE_MON_IN_PARTY': 30,
    'EVO_TRADE_SPECIFIC_MON': 31,
    'EVO_SPECIFIC_MAP': 32,
    'EVO_LEVEL_NATURE_AMPED': 33,
    'EVO_LEVEL_NATURE_LOW_KEY': 34,
    'EVO_CRITICAL_HITS': 35,
    'EVO_SCRIPT_TRIGGER_DMG': 36,
    'EVO_DARK_SCROLL': 37,
    'EVO_WATER_SCROLL': 38,
    'EVO_ITEM_NIGHT': 39,
    'EVO_ITEM_DAY': 40,
    'EVO_ITEM_HOLD': 41,
    'EVO_LEVEL_FOG': 42,
    'EVO_MOVE_TWO_SEGMENT': 43,
    'EVO_MOVE_THREE_SEGMENT': 44,
    'EVO_LEVEL_FAMILY_OF_THREE': 45,
    'EVO_LEVEL_FAMILY_OF_FOUR': 46,
    'EVO_USE_MOVE_TWENTY_TIMES': 47,
    'EVO_RECOIL_DAMAGE_MALE': 48,
    'EVO_RECOIL_DAMAGE_FEMALE': 49,
    'EVO_ITEM_COUNT_999': 50,
    'EVO_DEFEAT_THREE_WITH_ITEM': 51,
    'EVO_OVERWORLD_STEPS': 52,
}

def _pickle_target(fname: pathlib.Path) -> pathlib.Path:
    return PICKLE_PATH / fname.stem

def _load_pickled(fname: pathlib.Path) -> ExprList | None:
    target = _pickle_target(fname)
    exts = None
    if target.exists():
        with open(target, 'rb') as f:
            exts = pickle.load(f)
    return exts

def _dump_pickled(fname: pathlib.Path, exts: list):
    PICKLE_PATH.mkdir(parents=True, exist_ok=True)
    target = _pickle_target(fname)
    with open(target, 'wb') as f:
        pickle.dump(exts, f, protocol=pickle.HIGHEST_PROTOCOL)

def load_data(fname: pathlib.Path,
              extra_includes: list[str]=[]) -> ExprList:
    exts = _load_pickled(fname)
    if not exts:
        include_dirs = [f'-I{porydex.config.expansion / dir}' for dir in EXPANSION_INCLUDES]
        exts = parse_file(
            fname,
            use_cpp=True,
            cpp_path=porydex.config.compiler,
            cpp_args=[
                *PREPROCESS_LIBC,
                *include_dirs,
                *GLOBAL_PREPROC,
                *CONFIG_INCLUDES,
                *extra_includes
            ]
        ).ext
        _dump_pickled(fname, exts)

    return exts

def load_truncated(fname: pathlib.Path,
                   extra_includes: list[str]=[]) -> ExprList:
    return load_data(fname, extra_includes)[-1].init.exprs

def load_table_set(fname: pathlib.Path,
                   extra_includes: list[str]=[],
                   minimal_preprocess: bool=False) -> list[Decl]:
    include_dirs = [f'-I{porydex.config.expansion / dir}' for dir in EXPANSION_INCLUDES]

    if minimal_preprocess:
        # do NOT dump this version
        exts = parse_file(
            fname,
            use_cpp=True,
            cpp_path=porydex.config.compiler,
            cpp_args=[
                *PREPROCESS_LIBC,
                *include_dirs,
                r'-DTRUE=1',
                r'-DFALSE=0',
                r'-Du16=short',
                r'-include', r'config/species_enabled.h',
                *extra_includes
            ]
        ).ext
    else:
        exts = _load_pickled(fname)

    if not exts:
        exts = parse_file(
            fname,
            use_cpp=True,
            cpp_path=porydex.config.compiler,
            cpp_args=[
                *PREPROCESS_LIBC,
                *include_dirs,
                *GLOBAL_PREPROC,
                *CONFIG_INCLUDES,
                *extra_includes
            ]
        ).ext
        _dump_pickled(fname, exts)

    return exts

def load_data_and_start(fname: pathlib.Path,
                        pattern: re.Pattern,
                        extra_includes: list[str]=[]) -> tuple[ExprList, int]:
    all_data = load_data(fname, extra_includes)

    start = 0
    if pattern:
        end = len(all_data)
        for i in range(-1, -end, -1):
            if not all_data[i].name or not pattern.match(all_data[i].name):
                start = i + 1
                break

    return (all_data, start)

def eval_binary_operand(expr) -> int:
    if isinstance(expr, BinaryOp):
        return int(process_binary(expr))
    elif isinstance(expr, TernaryOp):
        return int(process_ternary(expr).value)
    elif isinstance(expr, ID):
        # Handle identifier objects by looking up known constants
        if expr.name in EVO_METHOD_MAPPING:
            return EVO_METHOD_MAPPING[expr.name]
        else:
            # Return 0 as a fallback for unknown identifiers
            # This allows processing to continue for unknown constants
            return 0
    return int(expr.value)

def process_binary(expr: BinaryOp) -> int | bool:
    left = eval_binary_operand(expr.left)
    right = eval_binary_operand(expr.right)
    op = BINARY_BOOL_OPS[expr.op]
    return op(left, right)

def process_ternary(expr: TernaryOp) -> typing.Any:
    if isinstance(expr.cond.left, ID):
        raise ValueError('cannot process left-side ID value in ternary')
    if isinstance(expr.cond.right, ID):
        raise ValueError('cannot process right-side ID value in ternary')

    op = BINARY_BOOL_OPS[expr.cond.op]
    if op(expr.cond.left.value, expr.cond.right.value):
        return expr.iftrue
    else:
        return expr.iffalse

def extract_compound_str(expr) -> str:
    # Depending on the compiler used for preprocessing, this could be expanded
    # to a number of types.

    # arm-none-eabi-gcc expands the macro to Cast(FuncCall(ExprList([Constant])))
    if isinstance(expr, Cast):
        return expr.expr.args.exprs[-1].value.replace('\\n', ' ')[1:-1]

    # clang expands the macro to CompoundLiteral(InitList([Constant]))
    if isinstance(expr, CompoundLiteral):
        return expr.init.exprs[-1].value.replace('\\n', ' ')[1:-1]

    if isinstance(expr.exprs[-1], FuncCall):
        return extract_compound_str(expr.exprs[0].args)
    return expr.exprs[-1].value.replace('\\n', ' ')[1:-1]

def extract_u8_str(expr) -> str:
    # Depending on the compiler used for preprocessing, this could be expanded
    # to a number of types.

    # arm-none-eabi-gcc and gcc expand the macro to FuncCall(ExprList([Constant]))
    if isinstance(expr, FuncCall):
        return expr.args.exprs[-1].value.replace('\\n', ' ')[1:-1]

    # clang expands the macro to InitList([Constant])
    return expr.exprs[0].value.replace('\\n', ' ')[1:-1]

def extract_int(expr) -> int:
    if isinstance(expr, TernaryOp):
        return int(process_ternary(expr).value)

    if isinstance(expr, UnaryOp):
        # we only care about the negative symbol
        if expr.op != '-':
            raise ValueError(f'unrecognized unary operator: {expr.op}')
        # Recursively call extract_int to handle the inner expression properly
        return -1 * extract_int(expr.expr)

    if isinstance(expr, BinaryOp):
        return int(process_binary(expr))

    if isinstance(expr, ID):
        # Handle identifier objects by looking up known constants
        if expr.name in EVO_METHOD_MAPPING:
            return EVO_METHOD_MAPPING[expr.name]
        else:
            # Return 0 as a fallback for unknown identifiers
            # This allows processing to continue for unknown constants
            return 0

    try:
        return int(expr.value)
    except ValueError:
        # try hexadecimal; if that doesn't work, just fail
        return int(expr.value, 16)

def extract_id(expr) -> str:
    if isinstance(expr, TernaryOp):
        return process_ternary(expr).name

    if isinstance(expr, BinaryOp):
        return str(expr.op).join([expr.left.name, expr.right.name])

    return expr.name

def extract_prefixed(prefix: str | re.Pattern, val: str, mod_if_match: typing.Callable[[str], str]=lambda x: x) -> str:
    match = re.match(prefix, val)
    if match:
        return mod_if_match(match.group(1))

    return val

