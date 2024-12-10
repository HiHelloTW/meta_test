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
from typing import ClassVar
from pydantic import BaseModel
import asyncio
import platform

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


class Communicate(Action):
    PROMPT_TEMPLATE: str = """
    ## BACKGROUND
    Suppose you are a team with {name}, you are in a negotiate with {opponent_name}.
    <NNEGOTIATE HISTORY>
    Previous rounds:
    {context}
    </NNEGOTIATE HISTORY>
    ## YOUR TURN
    閱讀完整個<NNEGOTIATE HISTORY> 到 </NNEGOTIATE HISTORY> 的內容，如果 <NNEGOTIATE HISTORY> 到 </NNEGOTIATE HISTORY> 有出現 {name} 和 {opponent_name} 回答下面問題 1，沒有的話回答下面問題 2
    1.請以客觀的角度判斷誰能處理 Task，從 {name} 和 {opponent_name} 挑出一位輸出你認為最有資格的腳色.
    2.請說出30個字判斷自己能不能執行這個 Task.
    """
    def __init__(self, name="Communicate", context=None, llm=None, **kwargs):
        super().__init__(**kwargs)
        self.name = name
        self.context = context
        self.llm = llm
        
    async def run(self, context: str, name: str, opponent_name: str):

        prompt = self.PROMPT_TEMPLATE.format(context=context, name=name, opponent_name=opponent_name)

        rsp = await self._aask(prompt)

        write_document_append("twoRolesCommunicate_docs", "example.txt", 'prompt: ' + prompt + '\n rsp ' + name + ': ' + rsp)
        
        return rsp

class Debator(Role):    
    name: str = ""
    profile: str = ""
    opponent_name: str = ""
    
    def __init__(
        self,
        **kwargs,
    ):
        super().__init__(**kwargs)
        self.set_actions([Communicate])
        self._watch([UserRequirement, Communicate])

    async def _observe(self) -> int:
        await super()._observe()
        # accept messages sent (from opponent) to self, disregard own messages from the last round
        self.rc.news = [msg for msg in self.rc.news if msg.send_to == {self.name}]
        return len(self.rc.news)
    
    async def _act(self) -> Message:
        logger.info(f"{self._setting}: to do {self.rc.todo}({self.rc.todo.name})")
        todo = self.rc.todo  # An instance of SpeakAloud

        memories = self.get_memories()
        context = "\n".join(f"{msg.sent_from}: {msg.content}" for msg in memories)
        # print(context)

        rsp = await todo.run(context=context, name=self.name, opponent_name=self.opponent_name)        

        msg = Message(
            content=rsp,
            role=self.profile,
            cause_by=type(todo),
            sent_from=self.name,
            send_to=self.opponent_name,
        )
        self.rc.memory.add(msg)

        return msg
    
async def debate(idea: str, investment: float = 3.0, n_round: int = 5):
    EdenProfile: str = 'You olny write code.'
    AdanProfile: str = 'You olny write text.'
    
    Eden = Debator(name="Eden", profile=EdenProfile, opponent_name="Adan")
    Adan = Debator(name="Adan", profile=AdanProfile, opponent_name="Eden")

    team = Team()
    team.hire([Eden,Adan])
    team.invest(investment)
    team.run_project(idea, send_to ="Eden")
    await team.run(n_round=n_round)




def main(
    idea: str = "Task: Write a text",
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