import sys
from gradio_config import CSS, OBJECT_INFO, BUBBLE_CSS, init, ROLE_2_NAME
import gradio as gr
sys.path.append("../../src/agents")
# from agent import Agent
# from sop import SOP, controller
# from serving import autorun, init_agents
import time
# import sys
import os
import re

# sys.path.append("../../src/agents")
from agent import Agent
from sop import SOP, controller
# CURRENT_NODE = ""

def autorun(sop: SOP, controller: controller,begin_name,begin_role,begin_query):
    current_node = sop.current_node
    print(current_node.name)
    current_memory = {"role": "user", "content": f"{begin_name}({begin_role}):{begin_query}"}
    sop.update_memory(current_memory)
    
    while True:
        next_node, next_role = controller.next(sop)
        if next_node != current_node:
            sop.send_memory(next_node)
        current_node = next_node
        sop.current_node = current_node
        current_agent = sop.agents[current_node.name][next_role]
        response = current_agent.step(
            # sop.shared_memory["chat_history"][-1]["content"], 
            current_node, sop.temperature
        )
        all = f""
        change_human = True
        for res in response:
            all += res
            yield res, next_role, next_node, change_human
            change_human = False
            # print(res, end="")
            time.sleep(0.02)
        print()
        current_memory = (
            {"role": "user", "content": all}
        )
        
        sop.update_memory(current_memory)
        
def init_agents(sop):
    for node_name,node_agents in sop.agents_role_name.items():
        for name,role in node_agents.items():
            agent = Agent(role,name)
            if node_name not in sop.agents:
                sop.agents[node_name] = {}
            sop.agents[node_name][role] = agent

"""全局的对话，只用于回答"""
global_dialog = {
    "user":[], 
    "agent":{
        
    },
    "system":[]
}

"""为每个输出弄一个css"""
def wrap_css(content, name) -> str:
    """content: 输出的内容 name: 谁的输出"""
    """确保name这个人是存在的"""
    assert name in OBJECT_INFO, f"'{name}' not in {OBJECT_INFO.keys()}"
    """取出这个人的全部信息"""
    output = ""
    info = OBJECT_INFO[name]
    if info["id"] == "USER":
        # 背景颜色 名字颜色 名字 字体颜色 字体大小 内容 图片地址
        output = BUBBLE_CSS["USER"].format(
            info["bubble_color"],
            info["text_color"],
            name,
            info["text_color"],
            info["font_size"],
            content,
            info["head_url"]
        )
    elif info["id"] == "SYSTEM":
        # 背景颜色 字体大小 字体颜色 名字 内容
        output = BUBBLE_CSS["SYSTEM"].format(
            info["bubble_color"],
            info["font_size"],
            info["text_color"],
            name,
            content
        )
    elif info["id"] == "AGENT":
        # 图片地址 背景颜色 名字颜色 名字 字体颜色 字体大小 内容
        output = BUBBLE_CSS["AGENT"].format(
            info["head_url"],
            info["bubble_color"],
            info["text_color"],
            name,
            info["text_color"],
            info["font_size"],
            content,
        )
    else:
        assert False
    return output

def get_new_message(message, history, choose, require):
    """将用户的输入存下来"""
    global_dialog["user"].append(message)
    return gr.Textbox.update(interactive=False), \
        history + [[wrap_css(name="User", content=message), None]], \
            gr.Radio.update(interactive=False), \
                gr.Textbox.update(interactive=False)

def get_response(history, summary_history, choose, require, msg):
    """此处的history都是有css wrap的，所以一般都不会用，只要是模型的输出"""
    global sop
    # agent_response = generate_response(history)
    for agent_response in generate_response(history, choose, require, msg):
        # time.sleep(0.05)
        # print(agent_response)
        if agent_response is None:
            """节点切换"""
            history.append((None, ""))
            summary_history.append((None, wrap_css(f"{sop.shared_memory['summary']}", name="Recorder")))
            print("mmmmm:", sop.shared_memory['summary'])
            # assert False
            yield history, summary_history  #, \
                # gr.Textbox.update(visible=True, interactive=False), \
                #     gr.Radio.update(visible=True, interactive=False), \
                #         gr.Textbox.update(visible=True, value="nihao", interactive=False)
        else:
            
            if len(agent_response) >= 2:
                print("mIKE",CURRENT_NODE)
                output = f"**{CURRENT_NODE}**<br>"
            else:
                output = ""
            
            for item in agent_response:
                for name in item:
                    content = item[name].replace('\n','<br>')
                    output = f"{output}<br>{wrap_css(content=content, name=name)}"
            # for name in global_dialog["agent"]:
            #     if name not in agent_response:
            #         global_dialog["agent"][name].append(None)
            #     else:
            #         global_dialog["agent"][name].append(agent_response[name])
            #         output = f"{output}<br>{wrap_css(content=agent_response[name], name=name)}"
            
            if output == "":
                """表示没有输出"""
                output = wrap_css(content="没有任何输出", name="System")
            
            history[-1] = (history[-1][0], output)
            yield history, summary_history  #, \
                # gr.Textbox.update(visible=True, interactive=False), \
                #     gr.Radio.update(visible=True, interactive=False), \
                #         gr.Textbox.update(visible=True, value="nihao", interactive=False)

def change_enviroment_prompt(new_prompt: str):
    global sop
    sop.environment_prompt = new_prompt
    for key in sop.nodes:
        sop.nodes[key].environment_prompt = new_prompt
    
 
def generate_response(history, choose, require, msg):
    def extract_strings(input_string):
        pattern = r'(\w+)\((\w+)\)'
        match = re.match(pattern, input_string)
        
        if match:
            groups = match.groups()
            return groups[0], groups[1]
        else:
            return None, None
    """模型要做的，传入的就是gloabl_dialog"""
    global sop, controller
    # response = {"Mike": "这是来自Mike的输入。第一行很长<br>这是一个测试的例子", 
    #         "John": "这是来自John的输入。第一行很长。<br>这是一个测试的例子"
    #         }
    
    # return_dict = {}
    # for name in response:
    #     return_dict[name] = ""
    #     for i, _ in enumerate(response["Mike"]):
    #         return_dict[name] = response[name][0:i+1]
    #         yield return_dict
    # query = global_dialog["user"][-1]
    content = ""
    wait = "."
    outputs = []
    current_role = None
    current_node = None
    if msg.strip() != "":
        change_enviroment_prompt(msg)
    else:
        msg = sop.environment_prompt
    # choose name（role）
    begin_name, begin_role = extract_strings(choose.replace("（","(").replace("）",")"))
    begin_query = require
    print("name:", begin_name, "\nrole:", begin_role, "\nquery:", begin_query, "\nmsg:", msg)
    for i, role, node, change_human in autorun(
        sop, controller, 
        # begin_role="大纲写作者1", 
        begin_role=begin_role,
        # begin_name="小亮", 
        begin_name=begin_name,
        # begin_query="请根据要求，先确定人物，然后基于人物再撰写第一版大纲",
        begin_query=begin_query
    ):
        # if current_role is not None and current_role != role:
        #     """表明切换了"""
        # print(role)
        print(role, node.name)
        if current_node is None:
            current_node = node.name
        """发生了节点的切换"""
        if current_node is not None and node.name != current_node:
            """发生了节点的切换"""
            yield None
            outputs.clear()
            current_node = node.name
            current_role = role
            content = ""
            outputs.append({ROLE_2_NAME[role]:content})
            """发生了角色的切换"""
        elif current_role != role:
            current_role = role
            content = ""
            outputs.append({"System":f"系统决定由{current_role}:{ROLE_2_NAME[current_role]}来回答"})
            outputs.append({ROLE_2_NAME[role]:content})
            """同一个人讲了两次"""
        elif change_human:
            content = ""
            outputs.append({ROLE_2_NAME[role]:content})
        #     if role in outputs:
        #         """"""
        content += i
        outputs[-1][ROLE_2_NAME[current_role]] = content
        global CURRENT_NODE
        CURRENT_NODE = current_node
        yield outputs
        # if ":" in content:
        # wait = "."
        
        # yield {ROLE_2_NAME[role]: content[content.find(":")+1:]}
        # for item in outputs:
        #     if 
        # if role not in outputs:
        #     outputs[role] = ""
        #     content = ""
        # outputs[role] = content
        # yield outputs
        # else:
            # if len(wait) == 6:
            #     wait = ""
            # wait += "."
            # yield {"wait": wait}

if __name__ == '__main__':
    sop = SOP("story.json")
    controller = controller(sop.controller_dict)
    init_agents(sop)
    """前端展示"""
    first_node_role = init("story.json")
    
    for name in OBJECT_INFO:
        if name not in ["System", "User"]:
            global_dialog["agent"][name] = []
    print(global_dialog)
    
    with gr.Blocks(css=CSS) as demo:
        with gr.Row():
            with gr.Column():
                chatbot = gr.Chatbot(elem_id="chatbot1", label="对话")  # elem_id="warning", elem_classes="feedback"
            
                msg = gr.Textbox(label="输入你的要求", placeholder=f"{sop.environment_prompt}", value=f"{sop.environment_prompt}")
                # clear = gr.Button("Clear")
                # with gr.Row().style(equal_height=True):
                choose = gr.Radio([f"{ROLE_2_NAME[_]}（{_}）" for _ in first_node_role], value=f"{ROLE_2_NAME[first_node_role[0]]}（{first_node_role[0]}）",label="开始Agent")
                require = gr.Textbox(label="开始指令", placeholder="请根据要求，先确定人物，然后基于人物再撰写第一版大纲", value="请根据要求，先确定人物，然后基于人物再撰写第一版大纲")

            chatbot_2 = gr.Chatbot(elem_id="chatbot1", label="核心记录").style(height='auto')
            """第一个参数指的是函数，第二个参数是输入Component，第三个是输出Component"""
            """submit是单击时的操作，then是单击后的操作。chatbot一个是要两次的结果，就是用户输入展示一次，回复再展示一次"""
            msg.submit(get_new_message, [msg, chatbot, choose, require], [msg, chatbot, choose, require], queue=False).then(
                get_response, [chatbot, chatbot_2, choose, require, msg], [chatbot, chatbot_2]
            )
    
    demo.queue()
    demo.launch()
    