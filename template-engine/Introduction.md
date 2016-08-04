### 引擎的实现方法：

模板的处理流程大方向上分为两部分：**解析阶段**与**渲染阶段**

渲染模板需要考虑以下几方面：

- 管理数据来源（即上下文环境）

- 处理逻辑（条件判断、循环）的部分

- 实现点取得成员属性或者键值的功能、实现过滤器调用

问题的关键在于从解析阶段到渲染阶段是如何过渡的。

解析得到了什么？渲染又是在渲染什么？

解析阶段可能有两种不同的做法：

> ### `解释或者是编译，这正对应了我们的程序语言的实现方式。`

> 在解释型模型中，解析阶段最后会生成能够反映模板结构的数据结构。
>
> 渲染阶段会遍历整个数据结构并基于预设的指令集生成最后的结果文本。Django使用的模板引擎使用的就是这种方式。

> 在编译模型中，解析阶段最后会生成某种可直接运行的代码。
>
> 渲染阶段可直接运行代码得到结果文本。Jinja2与Mako就是使用这种方式的两个典型。

我们使用第二种，也就是编译的方式来实现我们的模板引擎，核心归结下来还是这两部分：

- 解析模板，编译生成渲染代码


- 配合上下文执行渲染代码得到目标文本


先来看一个从模板到Python函数的例子，还是拿之前的例子举例。

模版文本：

```html
<p>Welcome, {{user_name}}!</p>
<p>Products:</p>
<ul>
{% for product in product_list %}
	<li>{{ product.name }}:
    	{{ product.price|format_price }}</li>
{% endfor %}
</ul>
```

模板编译后生成的Python函数：

```python
def render_function(context, do_dots):
	c_user_name = context['user_name']
	c_product_list = context['product_list']
	c_format_price = context['format_price']

	result = []
	append_result = result.append
	extend_result = result.extend
	to_str = str

	extend_result([
		'<p>Welcome, ',
		to_str(c_user_name),
		'!</p>\n<p>Products:</p>\n<ul>\n'
	])
	for c_product in c_product_list:
		extend_result([
			'\n    <li>',
			to_str(do_dots(c_product, 'name')),
			':\n        ',
			to_str(c_format_price(do_dots(c_product, 'price'))),
 			'</li>\n'
		])
	append_result('\n</ul>\n')
	return ''.join(result)
```
模板引擎的控制核心在于Templite 类，分为编译与渲染两个阶段。

Templite类的接口很简单，就是输入模板文本和可能会用到的函数或者常量组成的词典来初始化对象，调用render函数导入上下文得到结果文本。

CodeBuilder类（代码构建器）是为了方便Templite生成代码而编写的小工具，它的工作主要有添加代码、控制缩进、返回完整的代码字符串等。

测试命令：`python -m unittest test_templite`

参考资料：http://aosabook.org/en/500L/a-template-engine.html