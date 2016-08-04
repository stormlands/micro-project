# -*- coding: utf-8 -*-
import re


class TempliteSyntaxError(ValueError):
    pass


class CodeBuilder(object):
    """Build source code conveniently."""

    def __init__(self, indent=0):
        self.code = []
        self.indent_level = indent

    def __str__(self):
        return ''.join(str(c) for c in self.code)

    def add_line(self, line):
        """Add a line of source to the code.
        Indentation and newline will added for you, don't need provide them.
        """
        self.code.extend([' ' * self.indent_level, line, '\n'])

    def add_section(self):
        """Add a section , a sub-CodeBuilder."""
        section = CodeBuilder(self.indent_level)
        self.code.append(section)
        return section

    INDENT_STEP = 4  # PEP8 标准4空格缩进

    # 增加一级缩进
    def indent(self):
        self.indent_level += self.INDENT_STEP

    # 减小一级缩进
    def dedent(self):
        self.indent_level -= self.INDENT_STEP

    def get_globals(self):
        """Execute the code, and return a dict of the gloabals it defines."""
        # 检查缩进，保证所有块(block)都已经处理完成
        assert self.indent_level == 0
        # 得到生成的代码的字符串表示
        python_source = str(self)
        # 运行代码后得到名字空间地址（变量的字典）
        global_namespace = {}
        exec(python_source, global_namespace)
        return global_namespace


# Templite类的代码分为编译与渲染两个阶段
class Templite(object):

    def __init__(self, text, *contexts):
        """Construct a Templite with the given 'template text'.
        'contexts' are dictionaries of values to use for furture renderings.
        """
        self.context = {}
        for context in contexts:
            self.context.update(context)

        # 模板中所有的变量
        self.all_vars = set()
        # 属于循环的变量名
        self.loop_vars = set()

        code = CodeBuilder()

        code.add_line("def render_function(context, do_dots):")
        code.indent()
        # 加一个section占位，提取上下文变量的代码之后实现
        vars_code = code.add_section()
        code.add_line("result = []")
        code.add_line("append_result = result.append")
        code.add_line("extend_result = result.extend")
        code.add_line("to_str = str")

        buffered = []

        # 分析模板时，分析的结果暂存在一段缓冲区中，每分析完一段就通过flush_output函数往code中添加新代码
        def flush_output():
            """Force 'buffered' to the CodeBuilder."""
            if len(buffered) == 1:
                code.add_line("append_result(%s)" % buffered[0])
            if len(buffered) > 1:
                code.add_line("extend_result([%s])" % ', '.join(buffered))
            del buffered[:]

        # 使用栈来检查嵌套
        ops_stack = []

        # 使用正则表达式将模板文本分解成一系列token
        tokens = re.split(r"(?s)({{.*?}}|{%.*?%}|{#.*?#})", text)

        for token in tokens:
            # 注释不作处理
            if token.startswith('{#'):
                continue
            # 处理数据替换{{ ... }}
            elif token.startswith('{{'):
                expr = self._expr_code(token[2:-2].strip())
                buffered.append("to_str(%s)" % expr)
            # 处理控制结构{% ... %}
            elif token.startswith('{%'):
                flush_output()
                words = token[2:-2].strip().split()
                if words[0] == 'if':
                    # 这里的if只能支持一个表达式，如果words大于2就直接报错
                    if len(words) != 2:
                        self._syntax_error("Don't understand if", token)
                    ops_stack.append('if')
                    code.add_line('if %s:' % self._expr_code(words[1]))
                    code.indent()
                elif words[0] == 'for':
                    if len(words) != 4 or words[2] != 'in':
                        self._syntax_error("Don't understand for", token)
                    ops_stack.append('for')
                    self._variable(words[1], self.loop_vars)
                    code.add_line('for c_%s in %s:' % (words[1], self._expr_code(words[3])))
                    code.indent()
                elif words[0].startswith('end'):
                    if len(words) != 1:
                        self._syntax_error("Don't understand end", token)
                    end_what = words[0][3:]
                    # 先检查栈是否为空
                    if not ops_stack:
                        self._syntax_error("Too many ends", token)
                    start_what = ops_stack.pop()
                    if start_what != end_what:
                        self._syntax_error("Mismatched end tag", end_what)
                    code.dedent()
                else:
                    self._syntax_error("Don't understand tag", words[0])
            else:
                # 注意需要使用repr函数在字符串外面加一层引号
                if token:
                    buffered.append(repr(token))

        if ops_stack:
            self._syntax_error("Unmatched action tag", ops_stack[-1])

        flush_output()

        # 根据它们的差集提取数据，vars_code就是之前得到的section占位
        for var_name in self.all_vars - self.loop_vars:
            vars_code.add_line("c_%s = context[%r]" % (var_name, var_name))

        code.add_line("return ''.join(result)")
        code.dedent()
        # 从名字空间中得到渲染函数
        self._render_function = code.get_globals()['render_function']

    # 将模板中的表达式转化为python代码中的表达式
    def _expr_code(self, expr):
        if '|' in expr:
            pipes = expr.split("|")
            # 可能有多个filter，将_expr_code 设计成递归调用的函数
            code = self._expr_code(pipes[0])
            for func in pipes[1:]:
                self._variable(func, self.all_vars)
                code = 'c_%s(%s)' % (func, code)
        elif '.' in expr:
            dots = expr.split('.')
            code = self._expr_code(dots[0])
            args = ', '.join(repr(d) for d in dots[1:])
            code = 'do_dots(%s, %s)' % (code, args)
        else:
            self._variable(expr, self.all_vars)
            code = 'c_%s' % expr
        return code

    def _syntax_error(self, msg, thing):
        """Raise a syntax error using 'msg', and showing 'thing'."""
        raise TempliteSyntaxError("%s: %r" % (msg, thing))

    # 验证变量名是否有效，并将变量存入指定的变量集中
    def _variable(self, name, vars_set):
        """Track that 'name' is used as a variable.
        Adds the 'name' to var_set, a set of variable names.
        Raise a syntax error if 'name' is not a valid name.
        """
        if not re.match(r'[_a-zA-Z][_a-zA-Z0-9]*$', name):
            self._syntax_error("Not a valid name", name)
        vars_set.add(name)

    # 渲染阶段，只需要实现render与_do_dots就可以了
    def render(self, context=None):
        """Render this template by applying it to 'context'.
        'context' is a dictionary of values to use in this rendering.
        """
        render_context = dict(self.context)
        if context:
            render_context.update(context)
        return self._render_function(render_context, self.do_dots)

    def do_dots(self, value, *dots):
        """Evaluate dotted expressions at runtime"""
        for dot in dots:
            try:
                value = getattr(value, dot)
            except AttributeError:
                value = value[dot]
            if callable(value):
                value = value()
        return value
