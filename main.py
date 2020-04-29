import re
from functools import reduce
from random import randint, shuffle
from contextlib import suppress, contextmanager
from pprint import pprint
from collections.abc import Iterable


file_name = 'code.cpp'

with open('code.cpp', 'r') as file:
    code = file.read()


def rand_chance(how_many, from_amount):
    return randint(1, from_amount) < how_many


def throw_coin():
    return rand_chance(1, 2)


key_words = [
    'class', 'for', 'if', 'else', 'public', 'private', 'while', 'do', 'struct'
]


class RefSetting:
    indent = 4


class StrIterator:
    def __init__(self, text, index):
        self.text = text
        self.index = index

    def shift(self, value):
        self.index += value

    def copy(self):
        return StrIterator(self.text, self.index)

    def fill_from(self, other):
        self.index = other.index

    @property
    def string(self):
        if self.index >= len(self.text):
            print('OUT OF RANGE')
            raise NotFitException
        return self.text[self.index:]

    def is_end(self):
        return self.index >= len(self.text)


class NotFitException(Exception):
    pass


def merge(*items, **kwargs):
    res = []
    prefix = ''
    for item in items:
        if isinstance(item, str):
            res.append(prefix + item)
        elif isinstance(item, CodePart):
            res.append(item.refactor(**kwargs))
        elif isinstance(item, Iterable):
            res.append(merge(*item, **kwargs))
        else:
            raise TypeError(item)

    return ''.join(res)


def refactor_list(items, prefix='', join=None, **kwargs):
    def adjust_value(value):
        return merge(value, **kwargs)

    res = list(
        map(
            lambda x: adjust_value(x.refactor(**kwargs)) if isinstance(x, CodePart) else adjust_value(x), items
        )
    )
    if join:
        res = join.join(res)
    return res


def add_word(need_add, word, prefix=False, postfix=False):
    if not need_add:
        return ''

    return word


def str_indent(indent):
    return ' ' * indent


def suppress_spaces(it):
    with suppress(NotFitException):
        fit(it, CSpaces, pass_spaces=False)


def fit_regex(it, regex):
    match = re.match(regex, it.string)
    if not match:
        raise NotFitException
    value = match.group(0)
    assert isinstance(value, str)
    it.shift(len(value))
    return value


def fit(it, template, block_it=False, allow_spaces=True, sep=None, pass_spaces=True):
    if block_it:
        it = it.copy()
    if pass_spaces:
        suppress_spaces(it)

    if type(template) is type and issubclass(template, CodePart):
        return template(it)

    elif isinstance(template, str):
        return fit_regex(it, template)

    elif isinstance(template, list):
        temp = template[0]
        items = [fit(it, temp)]
        while True:
            next_item = None
            with try_fit(it) as f:
                if allow_spaces:
                    suppress_spaces(it)

                if sep:
                    f(sep)
                    if allow_spaces:
                        suppress_spaces(it)
                next_item = [f(temp)]

            if not next_item:
                break
            items += next_item

        return items
    else:
        raise TypeError(template)


def have_item(it, item):
    with try_fit(it) as f:
        f(item)
    return f.success


def fit_choice(it, *templates):
    for temp in templates:
        with try_fit(it) as f:
            return f(temp)

    raise NotFitException


@contextmanager
def try_fit(it):
    it_copy = it.copy()

    def safe_fit(*args, **kwargs):
        return fit(it_copy, *args, **kwargs)

    safe_fit.success = True
    safe_fit.fail = False

    try:
        yield safe_fit
    except NotFitException:
        safe_fit.success = False
        safe_fit.fail = True
        pass
    else:
        it.fill_from(it_copy)


def specific_symbol(symbol):
    class SpecificSymbol(CSymbol):
        def __init__(self, it):
            super().__init__(it)
            if self.value != symbol:
                raise NotFitException

    return SpecificSymbol


def specific_word(word):
    class SpecificWord(CWord):
        def __init__(self, it):
            super().__init__(it)
            if self.value != word:
                raise NotFitException

    return SpecificWord


# @logger.logit
class CodePart:
    @classmethod
    def parse(cls, it):
        try:
            it_copy = it.copy()
            res = cls(it_copy)
            it.fill_from(it_copy)
            return res
        except NotFitException:
            return None

    def refactor(self, **kwargs):
        return merge(self.value, **kwargs)

    def __repr__(self):
        rep = self.refactor().replace('    ', ' ')
        n = '\n'
        return f'{self.__class__.__name__}({rep.replace(n, " ")[:100]})'

    def __str__(self):
        return self.refactor()


class CSpaces(CodePart):
    def __init__(self, it):
        self.value = fit_regex(it, r'\s+')


class CSymbol(CodePart):
    def __init__(self, it):
        self.value = fit(it, r'.|\n')


class CSemicolon(CodePart):

    def __init__(self, it):
        self.value = fit_regex(it, ';')


class CComma(CodePart):

    def __init__(self, it):
        self.value = fit_regex(it, ',')


class CWord(CodePart):
    def __init__(self, it):
        self.value = fit_regex(it, r'[a-zA-Z_]\w*')


class CInclude(CodePart):
    def __init__(self, it):
        fit(it, specific_symbol('#'))
        self.name = fit(it, specific_word('include'), allow_spaces=False)
        suppress_spaces(it)
        self.det1 = ''
        with try_fit(it) as f:
            self.det1 = f(specific_symbol('<'))
        if not self.det1:
            self.det1 = fit(it, specific_symbol('"'))
        suppress_spaces(it)
        self.value = fit(it, CWord)
        self.det2 = fit(it, CSymbol)

    def refactor(self, **kwargs):
        return f'#{self.name.refactor(**kwargs)} {self.det1.refactor(**kwargs)}{self.value.refactor(**kwargs)}{self.det2.refactor(**kwargs)}'


class CColon2(CodePart):

    def __init__(self, it):
        self.value = fit_regex(it, '::')


class CWordsList(CodePart):

    def __init__(self, it):
        self.items = fit(it, [CWord], sep=CComma)

    def refactor(self, **kwargs):
        return merge(', '.join(refactor_list(self.items)))


class CTypeFull(CodePart):
    def __init__(self, it):
        self.const = have_item(it, specific_word('const'))
        self.type = fit(it, CType)
        self.const |= have_item(it, specific_word('const'))
        self.link = have_item(it, specific_symbol('&'))
        self.pointer = have_item(it, specific_symbol('*'))

    def refactor(self, **kwargs):
        res = ''
        res += add_word(self.const, 'const ')
        res += self.type.refactor(**kwargs)
        res += add_word(self.link, ' &')
        res += add_word(self.pointer, ' * ')
        return res


class CType(CodePart):
    def __init__(self, it):
        self.args = None
        with try_fit(it) as f:
            self.namespace = f(CWord)
            f(CColon2)
        if f.fail:
            self.namespace = None

        with try_fit(it) as f:
            self.name = f(CWord)
            f(specific_symbol('<'))
            self.args = f([CType], sep=CComma)
            f(specific_symbol('>'))

        if f.fail:
            self.name = fit(it, CWord)

        if self.name.value in key_words:
            raise NotFitException

    def refactor(self, **kwargs):
        res = ''
        if self.namespace:
            res += self.namespace.refactor(**kwargs) + ' :: '
        res += self.name.refactor(**kwargs)
        if self.args:
            res += f' <{", ".join(refactor_list(self.args))}>'
        return res


class CFuncArgument(CodePart):
    def __init__(self, it):
        self.type = fit(it, CTypeFull)
        self.name = fit(it, CWord)

    def refactor(self, **kwargs):
        res = ''
        res += self.type.refactor(**kwargs) + ' '
        res += self.name.refactor(**kwargs)
        return res


class CFuncArguments(CodePart):
    def __init__(self, it):
        fit(it, specific_symbol('('))
        self.args = []
        with try_fit(it) as f:
            self.args = f([CFuncArgument], sep=CComma)
        fit(it, specific_symbol(')'))

    def refactor(self, **kwargs):
        return f"({', '.join(refactor_list(self.args))})"


class CFuncFullName(CodePart):
    def __init__(self, it):
        self.virtual = have_item(it, specific_word('virtual'))
        self.friend = have_item(it, specific_word('friend'))

        self.name = None
        with try_fit(it) as f:
            self.name = f(CMethodDestructor)
        if not self.name:
            with try_fit(it) as f: self.name = f(CMethodConstructor)
        if not self.name:
            with try_fit(it) as f: self.name = f(CFuncName)
        if not self.name:
            raise NotFitException

        self.const = have_item(it, specific_word('const'))

    def refactor(self, **kwargs):
        res = ''
        if self.virtual: res += 'virtual '
        if self.friend: res += 'friend '

        res += self.name.refactor(**kwargs)

        if self.const: res += ' const'

        return res


class CFuncNameString(CodePart):
    def __init__(self, it):
        self.operation = None
        self.word = None
        with try_fit(it) as f:
            f(specific_word('operator'))
            self.operation = f(r'[^(]+')
        if not f.success:
            self.word = fit(it, CWord)

    def refactor(self, **kwargs):
        if self.word:
            return self.word.refactor(**kwargs)
        return f'operator {self.operation}'


class CFuncName(CodePart):
    def __init__(self, it):
        self.c_type = fit(it, CTypeFull)
        with try_fit(it) as f:
            self.c_class = f(CWord)
            f(CColon2)

        if not f.success:
            self.c_class = None

        self.c_name = fit(it, CFuncNameString)
        self.c_args = fit(it, CFuncArguments)

    def refactor(self, **kwargs):
        if self.c_class:
            return '{} {}::{} {}'.format(*refactor_list([self.c_type, self.c_class, self.c_name, self.c_args]))
        else:
            return '{} {} {}'.format(*refactor_list([self.c_type, self.c_name, self.c_args]))


class CFuncDeclaration(CodePart):
    def __init__(self, it):
        self.func = fit(it, CFuncFullName)
        self.equal_zero = False
        self.default = False
        with try_fit(it) as f:
            f(specific_symbol('='))

        if f.success:
            self.equal_zero = have_item(it, specific_symbol('0'))
            if not self.equal_zero:
                self.default = True
                fit(it, specific_word('default'))

        fit(it, CSemicolon)

    def refactor(self, **kwargs):
        res = self.func.refactor(**kwargs)
        if self.equal_zero:
            res += ' = 0'
        elif self.default:
            res += ' = default'
        res += ';'
        return res


class CBody(CodePart):
    def __init__(self, it):
        fit(it, specific_symbol('{'))
        self.expressions = []
        with try_fit(it) as f:
            self.expressions = f([CCommand])
        fit(it, specific_symbol('}'))

    def refactor(self, indent=0, **kwargs):
        return '{\n' + \
               refactor_list(self.expressions, join='\n',
                             indent=indent + RefSetting.indent, **kwargs) + '\n' + \
               str_indent(indent) + '}'


class CBodyOrInstruction(CodePart):
    def __init__(self, it):
        self.body = None
        with try_fit(it) as f:
            self.body = f(CBody)

        self.exp = None
        if f.fail:
            self.exp = fit(it, CCommand)

    def refactor(self, indent=0, **kwargs):
        if self.body:
            return self.body.refactor(**kwargs, indent=indent)

        return self.exp.refactor(indent=indent + RefSetting.indent, **kwargs)


class CConstructionIfElse(CodePart):
    def __init__(self, it):
        fit(it, specific_word('if'))
        self.exp = fit(it, CExpressionInBrackets)
        self.body = fit(it, CBodyOrInstruction)
        self.else_body = None
        with try_fit(it) as f:
            f(specific_word('else'))
            self.else_body = f(CBodyOrInstruction)

    def refactor(self, **kwargs):
        res = f'if {self.exp.refactor(**kwargs)} {self.body.refactor(**kwargs)}'
        if self.else_body:
            res += f' else {self.else_body.refactor(**kwargs)}'
        return res


class CExpressionUntilBracket(CodePart):
    def __init__(self, it):
        s = fit_regex(it, r'[^)]+')
        while s.count('(') != s.count(')'):
            s += ')'
            it.shift(1)
            s += fit_regex(it, r'[^)]*')

        self.value = s


class CExpressionInBrackets(CodePart):
    def __init__(self, it):
        fit(it, specific_symbol('('))
        self.exp = CEmpty(it)
        with try_fit(it) as f:
            self.exp = f(CExpressionUntilBracket)

        fit(it, specific_symbol(')'))

    def refactor(self, **kwargs):
        return f'( {self.exp.refactor(**kwargs)} )'


class CFullExpression(CodePart):
    def __init__(self, it):
        with try_fit(it) as f:
            f(specific_symbol('}'))
        if f.success:
            raise NotFitException

        self.value = fit(it, r'[^;]*;')


class CCommand(CodePart):
    def __init__(self, it):
        with try_fit(it) as f:
            self.value = f(CConstructionIfElse)
        if f.fail:
            with try_fit(it) as f:
                self.value = f(CConstructionFor)
        if f.fail:
            with try_fit(it) as f:
                self.value = f(CFullExpression)
        if f.fail:
            raise NotFitException

    def refactor(self, indent=0, **kwargs):
        return str_indent(indent) + self.value.refactor()


class CFuncDeclarationAssignment(CodePart):
    def __init__(self, it):
        self.name = fit(it, CWord)
        self.exp = fit(it, CExpressionInBrackets)

    def refactor(self, **kwargs):
        return f'{self.name}{self.exp}'


class CFuncImplementation(CodePart):
    def __init__(self, it):
        self.name = fit(it, CFuncFullName)
        self.assignments = []
        with try_fit(it) as f:
            f(specific_symbol(':'))
            self.assignments = f([CFuncDeclarationAssignment], sep=CComma)
        self.body = fit(it, CBody)

    def refactor(self, **kwargs):
        res = self.name.refactor(**kwargs)
        if self.assignments:
            res += ': ' + refactor_list(self.assignments, join=', ')
        res += ' ' + self.body.refactor(**kwargs)
        return res


class CMethodDestructor(CodePart):
    def __init__(self, it):
        self.value = fit(it, specific_symbol('~')), fit(it, CMethodConstructor)


class CEmpty(CodePart):
    def __init__(self, it):
        self.value = ''


class CMethodConstructor(CodePart):
    def __init__(self, it):
        self.name = fit(it, CWord)
        self.args = fit(it, CFuncArguments)

    def refactor(self, **kwargs):
        return f'{self.name.refactor(**kwargs)} {self.args.refactor(**kwargs)}'


class CConstructionFor(CodePart):
    def __init__(self, it):
        fit(it, specific_word('for'))
        fit(it, specific_symbol('('))
        self.e1 = fit(it, CFullExpression)
        self.e2 = fit(it, CFullExpression)
        self.e3 = CEmpty(it)
        with try_fit(it) as f:
            self.e3 = f(CExpressionUntilBracket)

        fit(it, specific_symbol(')'))
        self.body = fit(it, CBodyOrInstruction)

    def refactor(self, **kwargs):
        return f'for ({self.e1.refactor()} {self.e2.refactor()} {self.e3.refactor()}) {self.body.refactor(**kwargs)}'


class CFunction(CodePart):
    def __init__(self, it):
        self.value = fit_choice(it, CFuncDeclaration, CFuncImplementation)


class CVariableInit(CodePart):
    def __init__(self, it):
        self.type = fit(it, CTypeFull)
        self.name = fit(it, CFullExpression)

    def refactor(self, **kwargs):
        return f'{self.type} {self.name}'


class CFuncOrVarInit(CodePart):
    def __init__(self, it):
        self.value = fit_choice(it, CFunction, CVariableInit)

    def refactor(self, indent=0, **kwargs):
        return str_indent(indent) + self.value.refactor(**kwargs, indent=indent)


class CClassAttributes(CodePart):
    def __init__(self, it):
        self.value = fit(it, [CFuncOrVarInit])


def generate_class_section(section_type):
    assert section_type == 'public' or section_type == 'private'

    class CClassParticularSection(CodePart):
        def __init__(self, it):
            self.section_type = section_type
            fit(it, specific_word(section_type))
            fit(it, specific_symbol(':'))
            self.attrs = CEmpty(it)
            with try_fit(it) as f:
                self.attrs = f(CClassAttributes)

        def refactor(self, **kwargs):
            return f'{section_type}:\n{self.attrs.refactor(**kwargs)}'

    return CClassParticularSection


class CClassSection(CodePart):
    def __init__(self, it):
        self.value = fit_choice(it, generate_class_section('public'), generate_class_section('private'))


class CClass(CodePart):
    def __init__(self, it):
        fit(it, specific_word('class'))
        self.name = fit(it, CWord)
        fit(it, specific_symbol('{'))
        self.private_sections = []
        self.public_sections = []
        self.sections = []
        with try_fit(it) as f:
            self.sections += f([CClassSection])
        with try_fit(it) as f:
            self.private_sections.append(f(CClassAttributes))
        with try_fit(it) as f:
            self.sections += f([CClassSection])

        fit(it, specific_symbol('}'))
        fit(it, CSemicolon)

    def refactor(self, **kwargs):
        private_sections = self.private_sections + list(
            filter(lambda x: x.value.section_type == 'private', self.sections))
        public_sections = self.public_sections + list(
            filter(lambda x: x.value.section_type == 'public', self.sections))

        public_attrs = sum(map(lambda x: x.value.attrs.value, public_sections), [])
        private_attrs = sum(map(lambda x: x.value.attrs.value, private_sections), [])
        shuffle(public_attrs)
        shuffle(private_attrs)
        res = f'class {self.name}' + ' {\n'
        res += 'private:\n' + refactor_list(private_attrs, join='\n', indent=RefSetting.indent)
        res += '\n\npublic:\n' + refactor_list(public_attrs, join='\n\n', indent=RefSetting.indent)
        res += '\n};'
        return res


c_elements = [
    CSpaces,
    CInclude,
    CClass,
    CFunction,
    CVariableInit,
    CWord,
    CSymbol
]

if __name__ == '__main__':
    code_elements = []
    iterator = StrIterator(code, 0)
    while not iterator.is_end():
        for CPart in c_elements:
            c_part = CPart.parse(iterator)
            if c_part:
                code_elements.append(c_part)
                break

    pprint(list(filter(lambda x: not isinstance(x, CSpaces), code_elements)))
    refactored_code = ''.join(map(lambda x: x.refactor(), code_elements))
    refactored_code_name = f'[{file_name.split(".")[0]}]refactored.{file_name.split(".")[-1]}'
    with open(refactored_code_name, 'w') as file:
        file.write(refactored_code)
