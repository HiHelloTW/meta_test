import re

from metagpt.actions import Action
from metagpt.roles import Role
from metagpt.actions import UserRequirement
from metagpt.schema import Message
import fire
import typer
from metagpt.logs import logger
from metagpt.team import Team
import os
import asyncio
import platform
from pathlib import Path
from metagpt.roles.product_manager import ProductManager

app = typer.Typer()

def write_document_append(directory, filename, content):
    """
    Write or append the given content to a file in the specified directory.
    If the file exists, append the content; otherwise, create a new file.
    
    Parameters:
    - directory (str): The directory where the file will be written.
    - filename (str): The name of the file.
    - content (str): The content to write or append to the file.
    """
    try:
        # 確保目錄存在
        if not os.path.exists(directory):
            os.makedirs(directory)
            print(f"Directory '{directory}' created.")
        
        # 組合完整檔案路徑
        file_path = os.path.join(directory, filename)
        
        # 決定寫入模式 ('a' 表示追加，'w' 表示覆蓋)
        mode = "a" if os.path.exists(file_path) else "w"
        
        # 將內容寫入檔案（追加新內容）
        with open(file_path, mode, encoding="utf-8") as writer:
            if mode == "a":
                writer.write("\n-------------------------------------------------\n")  # 如果是追加模式，先寫入一個換行
            writer.write(content)
        
        # 打印操作結果
        action = "Appended to" if mode == "a" else "Created"
        print(f"{action} file: {file_path}")
    except Exception as e:
        print(f"Error: {e}")


def parse_code(rsp):
    pattern = r"```python(.*)```"
    match = re.search(pattern, rsp, re.DOTALL)
    code_text = match.group(1) if match else rsp
    return code_text

def extract_tag_content(string):
    # 定義正則表達式，匹配 <XXX> 的模式
    match = re.search(r"<(.*?)>", string)
    if match:
        return match.group(1)  # 回傳匹配到的內容
    return None  # 如果沒有匹配到，回傳 None

class AssignJobs(Action):
    PROMPT_TEMPLATE: str = """
    ## 
    "你是一位高效能的領導者，擁有出色的組織能力和溝通技巧。
    你的責任是根據團隊成員的技能、興趣和工作負荷，明智地分配工作，確保專案成功並鼓勵團隊合作。
    在每次任務分配時，你會明確說明每個成員的角色、任務的目標、完成的期限，以及可供使用的資源。
    如果有成員需要幫助或資源不足，你會提出建議或調整計劃。以下是團隊背景與需要完成的任務："
    
    示例：
    "團隊背景：    
    {roles}
        
    需要完成的任務：
    {context}
    
    請開始分配任務，並確保考慮到團隊背景成員的強項"
    決定後只用 "<成員名稱>" 生成以下文字 
    例如:
    <Leader>。
    """
    def __init__(self, name="AssignJobs", context=None, llm=None, **kwargs):
        super().__init__(**kwargs)
        self.name = name
        self.context = context
        self.llm = llm
        
    async def run(self, context: str, roles: str):

        prompt = self.PROMPT_TEMPLATE.format(context=context, roles=roles)

        rsp = await self._aask(prompt)

        write_document_append("assignJobs_docs", "example.txt", 'prompt: ' + prompt + '\n rsp: ' + rsp)
        
        return rsp

class Leader(Role):
    name: str= ""
    profile: str = ""
    hire_roles: list[Role] = []
    
    def __init__(
        self,
        **kwargs,
    ):
        super().__init__(**kwargs)
        self._watch([UserRequirement])
        self.set_actions([AssignJobs])
    
    async def _act(self) -> Message:
        logger.info(f"{self._setting}: to do {self.rc.todo}")
        todo = self.rc.todo 

        memories = self.get_memories()
        context ="\n".join(f"{msg.sent_from}: {msg.content}" for msg in memories)
        
        roles = "\n".join(f"{hire_role.name}: {hire_role.profile}" for hire_role in self.hire_roles)
        
        rsp = await todo.run(context=context, roles=roles)       
        
        sendTo = extract_tag_content(rsp)
        
        msg = Message(
            content=context,
            role=self.profile,
            cause_by=type(todo),
            sent_from=self.name,
            send_to=sendTo,
        )
        
        self.rc.memory.add(msg)

        return msg

class SimpleWriteCode(Action):
    PROMPT_TEMPLATE: str = """
    {instruction}.
    Return ``` your_code_here ``` with NO other texts,
    your code:
    """

    name: str = "SimpleWriteCode"

    async def run(self, instruction: str):
        prompt = self.PROMPT_TEMPLATE.format(instruction=instruction)

        rsp = await self._aask(prompt)

        code_text = SimpleWriteCode.parse_code(rsp)

        write_document_append("assignJobs_docs", "example.txt",'prompt: ' + prompt + '\n rsp: ' + rsp)
        
        return code_text

    @staticmethod
    def parse_code(rsp):
        pattern = r"```python(.*)```"
        match = re.search(pattern, rsp, re.DOTALL)
        code_text = match.group(1) if match else rsp
        return code_text


class PythonCoder(Role):
    name: str = "Eden"
    profile: str = "Python Coder"

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.set_actions([SimpleWriteCode])
        self._watch([AssignJobs])

    async def _act(self) -> Message:
        logger.info(f"{self._setting}: to do {self.rc.todo}({self.rc.todo.name})")
        todo = self.rc.todo  # todo will be SimpleWriteCode()

        msg = self.get_memories(k=1)[0]  # find the most recent messages
        code_text = await todo.run(msg.content)
        msg = Message(content=code_text, role=self.profile, cause_by=type(todo))

        return msg
    
class JavaScriptCoder(Role):
    name: str = "Adan"
    profile: str = "JavaScript Coder"

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.set_actions([SimpleWriteCode])
        self._watch([AssignJobs])

    async def _act(self) -> Message:
        logger.info(f"{self._setting}: to do {self.rc.todo}({self.rc.todo.name})")
        todo = self.rc.todo  # todo will be SimpleWriteCode()

        msg = self.get_memories(k=1)[0]  # find the most recent messages
        code_text = await todo.run(msg.content)
        msg = Message(content=code_text, role=self.profile, cause_by=type(todo))

        return msg
    
async def debate(idea: str, investment: float = 3.0, n_round: int = 5):
    hire_roles = [PythonCoder(),JavaScriptCoder()] 
    
    leaderProfile: str = 'leader 負責分配工作'    
    leader = Leader(name="leader", profile=leaderProfile, hire_roles=hire_roles)

    team = Team()
    team.hire([leader] + hire_roles)
    team.invest(investment)
    team.run_project(idea, send_to ="leader")
    await team.run(n_round=n_round)




def main(
    idea: str = "將查克拉凝聚在手上，搓出螺旋丸",
    investment: float = 3.0,
    n_round: int = 5,
):
    """
    :param idea: Debate topic, such as "Topic: The U.S. should commit more in climate change fighting"
                 or "Trump: Climate change is a hoax"
    :param investment: contribute a certain dollar amount to watch the debate
    :param n_round: maximum rounds of the debate
    :return:
    """
    
    if platform.system() == "Windows":
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    asyncio.run(debate(idea, investment, n_round))


if __name__ == "__main__":
    fire.Fire(main)