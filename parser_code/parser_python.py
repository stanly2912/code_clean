# from pprint import pprint
# from tree_sitter import Language, Parser
# from index import get_node_content
# from circle import get_circle

# language = "python"

# my_language = Language('./builds/my-languages.so', language)
# parser = Parser()
# parser.set_language(my_language)
# query = my_language.query("(function_definition) @function")


# def get_child(node, child_types):
#     """
#     获取子节点
#     :param node:
#     :param child_types:
#     :return:
#     """
#     if not isinstance(child_types, list):
#         child_types = [child_types]
#     children = node.named_children
#     for child in children:
#         for child_type in child_types:
#             if child.type == child_type:
#                 return child
#     return None


# def parse_code(content):
#     """
#     解析代码
#     获取函数名、参数名、圈复杂度
#     :param content: 代码
#     :return:
#     """
#     function_datas = {}
#     tree = parser.parse(bytes(content, "utf8"))
#     captures = query.captures(tree.root_node)
#     for node, alias in captures:
#         start = node.start_point[0]
#         rows = node.end_point[0] - node.start_point[0] + 1
#         name = get_child(node, "identifier")
#         params = get_child(node, "parameters")
#         body = get_child(node, "block")
#         name = get_node_content(content, name)
#         params = [get_node_content(content, param) for param in params.named_children]
#         circle, statements = get_circle(body)
#         print(statements)
#         statements = [{"start": statement.start_point[0], "rows": statement.end_point[0] - statement.start_point[0] + 1, "type": statement.type, "content": content} for statement in statements]
#         # statements = [get_node_content(content, statement) for statement in statements]
#         circle = circle + 1
#         data = {
#             "params"           : params,
#             "circle"           : circle,
#             "circle_statements": statements,
#             "rows"             : rows,
#             "start"            : start,
#         }
#         if name:
#             function_datas[name] = data
#     return function_datas


# if __name__ == '__main__':
#     content = '''
#     def main(a, b): # hello
#         for _ in range(10):
#             if (a > b and a < b) or (a == b):
#                 print(1)
#                 return
#             elif a > b:
#                 print(2)
#             else:
#                 print(2)
#             b = a if a > b else b
#             for _ in range(10):
#                 print(a)
#         for _ in range(10):
#             for _ in range(10):
#                 print(a)
#     def main1(a, b):
#         for _ in range(10):
#             for _ in range(10):
#                 print(a)
#         for _ in range(10):
#             for _ in range(10):
#                 print(a)
#     '''
#     results = parse_code(content)
#     pprint(results)

from pprint import pprint
from tree_sitter import Language, Parser
from index import get_node_content
from circle import get_circle

language = "python"
DIR="/home/wangbn/code_clean/parser_code"


my_language = Language(DIR+'/builds/my-languages.so', language)
parser = Parser()
parser.set_language(my_language)
query = my_language.query("(function_definition) @function")


def get_child(node, child_types):
    """
    获取子节点
    :param node:
    :param child_types:
    :return:
    """
    if not isinstance(child_types, list):
        child_types = [child_types]
    children = node.named_children
    for child in children:
        for child_type in child_types:
            if child.type == child_type:
                return child
    return None


def parse_code(content):
    """
    解析代码
    获取函数名、参数名、圈复杂度、函数源代码
    :param content: 代码
    :return:
    """
    function_datas = {}
    # 1. 将代码按行分割，用于后续提取函数内容
    lines = content.splitlines()
    tree = parser.parse(bytes(content, "utf8"))
    captures = query.captures(tree.root_node)
    
    for node, alias in captures:
        start = node.start_point[0]
        rows = node.end_point[0] - node.start_point[0] + 1
        
        # 2. 根据 start 和 rows 切片提取函数源代码
        func_content = '\n'.join(lines[start: start + rows])
        
        name = get_child(node, "identifier")
        params = get_child(node, "parameters")
        body = get_child(node, "block")
        
        name = get_node_content(content, name)
        params = [get_node_content(content, param) for param in params.named_children]
        circle, statements = get_circle(body)
        
        # 修正：statement 内容需要单独提取（原代码直接赋了 content，这里修正为提取具体内容）
        statements = [
            {
                "start": statement.start_point[0],
                "rows": statement.end_point[0] - statement.start_point[0] + 1,
                "type": statement.type,
                "content": get_node_content(content, statement)  # 修正这里
            } 
            for statement in statements
        ]
        
        circle = circle + 1
        data = {
            "params": params,
            "circle": circle,
            "circle_statements": statements,
            "rows": rows,
            "start": start,
            "function_content": func_content  # 3. 新增：存储函数完整源代码
        }
        if name:
            function_datas[name] = data
    return function_datas


if __name__ == '__main__':
    content = '''
    def main(a, b): 
        # hello
        # hello
        for _ in range(10):
            if (a > b and a < b) or (a == b):
                print(1)
                return
            elif a > b:
                print(2)
            else:
                print(2)
            b = a if a > b else b
            for _ in range(10):
                print(a)
        for _ in range(10):
            for _ in range(10):
                print(a)
    def main1(a, b):
        for _ in range(10):
            for _ in range(10):
                print(a)
        for _ in range(10):
            for _ in range(10):
                print(a)
    '''
    results = parse_code(content)
    pprint(results)