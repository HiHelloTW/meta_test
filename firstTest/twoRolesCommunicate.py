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


class SubtracterCommunicate(Action):
    PROMPT_TEMPLATE: str = """
    ## BACKGROUND
    {prefix} Suppose you are a team with {opponent_name}, you are in a negotiate with {opponent_name}.
    <NEGOTIATE HISTORY>
    Previous rounds:
    {context}
    </NEGOTIATE HISTORY>
    ## YOUR TURN
    確認 <NEGOTIATE HISTORY> 到 </NEGOTIATE HISTORY> 中的問題，重複描述問題，只需要數學問題，重複描述己的專長，判斷自己是不是擅長解決此問題，擅長的話輸出 <yes> 或不擅長輸出 <no> 
    """
    def __init__(self, name="SubtracterCommunicate", context=None, llm=None, **kwargs):
        super().__init__(**kwargs)
        self.name = name
        self.context = context
        self.llm = llm
        
    async def run(self, context: str, name: str, opponent_name: str):

        prompt = self.PROMPT_TEMPLATE.format(context=context, name=name, opponent_name=opponent_name, prefix=self.prefix )

        rsp = await self._aask(prompt)

        write_document_append("twoRolesCommunicate_docs2", "example.txt", 'prompt: ' + prompt + '\n rsp ' + name + ': ' + rsp)
        
        return rsp

class AdderCommunicate(Action):
    PROMPT_TEMPLATE: str = """
    ## BACKGROUND
    {prefix} Suppose you are a team with {opponent_name}, you are in a negotiate with {opponent_name}.
    <NEGOTIATE HISTORY>
    Previous rounds:
    {context}
    </NEGOTIATE HISTORY>
    ## YOUR TURN
    確認 <NEGOTIATE HISTORY> 到 </NEGOTIATE HISTORY> 中的問題。重複描述問題，只需要數學問題，重複描述己的專長，判斷自己是不是擅長解決此問題，擅長的話輸出 <yes> 或不擅長輸出 <no> 
    """
    def __init__(self, name="AdderCommunicate", context=None, llm=None, **kwargs):
        super().__init__(**kwargs)
        self.name = name
        self.context = context
        self.llm = llm
        
    async def run(self, context: str, name: str, opponent_name: str):

        prompt = self.PROMPT_TEMPLATE.format(context=context, name=name, opponent_name=opponent_name, prefix=self.prefix)

        rsp = await self._aask(prompt)

        write_document_append("twoRolesCommunicate_docs2", "example.txt", 'prompt: ' + prompt + '\n rsp ' + name + ': ' + rsp)
        
        return rsp

class SubtracterDebator(Role):
    name: str = ""
    profile: str = ""
    opponent_name: str = ""
    
    def __init__(
        self,
        **kwargs,
    ):
        super().__init__(**kwargs)
        self.set_actions([SubtracterCommunicate])
        self._watch([UserRequirement, AdderCommunicate])

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
    
class AdderDebator(Role):
    name: str = ""
    profile: str = ""
    opponent_name: str = ""
    
    def __init__(
        self,
        **kwargs,
    ):
        super().__init__(**kwargs)
        self.set_actions([AdderCommunicate])
        self._watch([SubtracterCommunicate])

    async def _observe(self) -> int:
        await super()._observe()
        # accept messages sent (from opponent) to self, disregard own messages from the last round
        self.rc.news = [msg for msg in self.rc.news if msg.send_to == {self.name}]
        return len(self.rc.news)
    
    async def _act(self) -> Message:
        logger.info(f"{self._setting}: to do {self.rc.todo}({self.rc.todo.name})")
        todo = self.rc.todo  # An instance of SpeakAloud

        memories = self.get_memories()
        context ="\n".join(f"{msg.sent_from}: {msg.content}" for msg in memories)
        print(context)

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
    AdderProfile: str = 'number adder.你只會加法. You can olny add the number with math question.'
    SubtracterProfile: str = 'number subtracter.你只會減法. You can olny subtracter the number with math question .'
    
    Eden = SubtracterDebator(name="Eden", profile=SubtracterProfile, opponent_name="Adan")
    Adan = AdderDebator(name="Adan", profile=AdderProfile, opponent_name="Eden")

    team = Team()
    team.hire([Eden,Adan])
    team.invest(investment)
    team.run_project(idea, send_to ="Eden")
    await team.run(n_round=n_round)




def main(
    idea: str = "數學問題: 你有 10 顆蘋果吃了 5 顆，總共剩下幾顆",
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