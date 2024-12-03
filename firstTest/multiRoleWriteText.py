import re

from metagpt.context import Context
from metagpt.actions import Action
from metagpt.roles import Role
from metagpt.actions import UserRequirement
from metagpt.schema import Message
import fire
import typer
from metagpt.logs import logger
from metagpt.team import Team
import os
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

class SimpleWriteCode(Action):
    PROMPT_TEMPLATE: str = """
    Write a python function that can {instruction}.
    Return ```python your_code_here ``` with NO other texts,
    your code:
    """
    name: str = "SimpleWriteCode"

    async def run(self, instruction: str):
        prompt = self.PROMPT_TEMPLATE.format(instruction=instruction)

        rsp = await self._aask(prompt)
        write_document_append("output_docs", "example.txt", 'SimpleWriteCode: ' + rsp)

        code_text = parse_code(rsp)

        return code_text


class SimpleWriteTest(Action):
    PROMPT_TEMPLATE: str = """
    Context: {context}
    Write {k} unit tests using pytest for the given function, assuming you have imported it.
    Return ```python your_code_here ``` with NO other texts,
    your code:
    """

    name: str = "SimpleWriteTest"

    async def run(self, context: str, k: int = 3):
        prompt = self.PROMPT_TEMPLATE.format(context=context, k=k)

        rsp = await self._aask(prompt)
        write_document_append("output_docs", "example.txt", 'SimpleWriteTest: ' + rsp)

        code_text = parse_code(rsp)

        return code_text    

class SimpleWriteReview(Action):
    PROMPT_TEMPLATE: str = """
    Context: {context}
    Review the test cases and provide one critical comments:
    """

    name: str = "SimpleWriteReview"

    async def run(self, context: str):
        prompt = self.PROMPT_TEMPLATE.format(context=context)

        rsp = await self._aask(prompt)
        write_document_append("output_docs", "example.txt", 'SimpleWriteReview: ' + rsp)

        return rsp


class SimpleCoder(Role):
    name: str = "Eden-SimpleCoder"
    profile: str = "SimpleCoder"

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self._watch([UserRequirement, SimpleWriteReview])
        self.set_actions([SimpleWriteCode])


class SimpleTester(Role):
    name: str = "Eden-SimpleTester"
    profile: str = "SimpleTester"

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.set_actions([SimpleWriteTest])
        self._watch([SimpleWriteCode])
        # self._watch([SimpleWriteCode, SimpleWriteReview])  # feel free to try this too

    async def _act(self) -> Message:
        logger.info(f"{self._setting}: to do {self.rc.todo}({self.rc.todo.name})")
        todo = self.rc.todo

        # context = self.get_memories(k=1)[0].content # use the most recent memory as context
        context = self.get_memories()  # use all memories as context

        code_text = await todo.run(context, k=5)  # specify arguments
        msg = Message(content=code_text, role=self.profile, cause_by=type(todo))

        return msg

class SimpleReviewer(Role):
    name: str = "Eden-SimpleReviewer"
    profile: str = "SimpleReviewer"

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.set_actions([SimpleWriteReview])
        self._watch([SimpleWriteTest])


@app.command()
async def main(
    idea: str = "write code a function that sum the list",
    investment: float = 3.0,
    n_round: int = 5,
):
    logger.info(idea)

    team = Team()
    team.hire(
        [
            SimpleReviewer(),
            SimpleCoder(),
            SimpleTester(),
        ]
    )

    team.invest(investment=investment)
    team.run_project(idea)
    await team.run(n_round=n_round)

if __name__ == "__main__":
    fire.Fire(main)
