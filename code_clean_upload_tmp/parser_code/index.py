from tree_sitter import Language, Parser


def tree_to_token_index(root_node):
    '''
    定位代码token，返回token在代码中原始位置

    从root_node开始，深度遍历其孩子节点：
    1. 如果root_node没有孩子（root_node是叶节点）或者root_node是字符串或者注释，直接返回code_snippet对应的位置
        个人猜想：
        估计某些编程语言的string和comment类型的语法树只有单引号、双引号叶子节点，而该节点内容被忽略掉了
    2. 如果有孩子节点，深度遍历，回溯时获取结果

    使用的属性:
    root_node.start_point: tuple[int, int]
    root_node.end_point: tuple[int, int]

    参数: root_node: Node

    返回: code_tokens: list[tuple[tuple[int,int], tuple[int, int]]]
    '''

    # 我突然发现该代码没有检测到cpp的string（也就是"hell world"），所以我改了第一行的第二个条件
    # 其他编程语言可能会有改变，所以需要小心谨慎
    # 原代码行：
    # if (len(root_node.children) == 0 or root_node.type == 'string') and root_node.type != 'comment':

    if (len(root_node.children) == 0 or root_node.type.find('string') != -1) and root_node.type != 'comment':
        return [(root_node.start_point, root_node.end_point)]
    else:
        code_tokens = []
        for child in root_node.children:
            code_tokens += tree_to_token_index(child)
        return code_tokens


def index_to_code_token(index, code):
    '''
    从 tree_to_token_index 返回的token位置元组列表 以及 代码行 生成代码token
    这里第二个参数，GraphCodeBert项目源代码写的是code，不是line_of_code

    1. 如果token起止都在同一行
        定位该代码行，定位改行的起止列，获取token
    2. token跨行【比如Python三个单引号包围的注释、或者Javascript中的模板字符串等等】
        1) 定位首行的token所在列
        2) 循环遍历到目标行之前，所有内容
        3) 定位末行的token所在列
        以上内容拼接即可

    参数: index: list[tuple[tuple[int,int], tuple[int, int]]]
    参数: code: list[str]

    返回: s: str
    '''
    start_point = index[0]
    end_point = index[1]
    if start_point[0] == end_point[0]:
        s = code[start_point[0]][start_point[1]:end_point[1]]
    else:
        s = ""
        s += code[start_point[0]][start_point[1]:]
        for i in range(start_point[0] + 1, end_point[0]):
            s += code[i]
        s += code[end_point[0]][:end_point[1]]
    return s


def get_node(cpp_loc, node):
    tokens_index = tree_to_token_index(node)
    code_tokens = [index_to_code_token(x, cpp_loc) for x in tokens_index]
    code_tokens = "".join(code_tokens)
    print(node, code_tokens)


def get_node_content(content, node):
    if not node:
        return ""
    loction = content.split("\n")
    tokens_index = tree_to_token_index(node)
    code_tokens = [index_to_code_token(x, loction) for x in tokens_index]
    code_tokens = "".join(code_tokens)
    # print(node, code_tokens)
    return code_tokens


if __name__ == '__main__':
    # 声明CPP代码解析器
    CPP_LANGUAGE = Language('builds/my-languages.so', 'cpp')
    cpp_parser = Parser()
    cpp_parser.set_language(CPP_LANGUAGE)

    # 这c语言不是我写的
    cpp_code_snippet = '''
    int mian{
        piantf("hell world");
        remake O;
    }
    '''

    # 完成解析，获取根节点
    tree = cpp_parser.parse(bytes(cpp_code_snippet, "utf8"))
    root_node = tree.root_node

    # 获取token对应的位置
    tokens_index = tree_to_token_index(root_node)
    print(tokens_index)
    # 获取代码行
    cpp_loc = cpp_code_snippet.split('\n')
    # 获取对应每个位置下的token
    code_tokens = [index_to_code_token(x, cpp_loc) for x in tokens_index]
    # ['int', 'mian', '{', 'piantf', '(', '"hell world"', ')', ';', 'remake', 'O', ';', '}']
    print(code_tokens)
