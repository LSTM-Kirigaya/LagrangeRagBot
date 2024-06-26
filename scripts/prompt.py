from __future__ import annotations
from dataclasses import dataclass
import warnings
import random
import math

import yaml

@dataclass(frozen=True)
class IntentNode:
    name: str
    description: str | None
    children: list[IntentNode]
    parent: IntentNode | None
    stories: list[Story]

@dataclass(frozen=True)
class Story:
    message: str
    intent: str

class PromptEngine:
    path: str
    schema: IntentNode | None
    stories: list[Story]
    rejects: list[str]
    intent2id: dict[str, int]
    id2intent: dict[int, str]
    name2node: dict[str, IntentNode]

    def __init__(self, path: str) -> None:
        self.path = path
        self.config = yaml.load(open(path, 'r', encoding='utf-8'), yaml.Loader)
        self.intent2id = {}
        self.id2intent = {}
        self.name2node = {}
        self.schema = self.handle_schema(self.config['schema'])
        self.stories = self.handle_stories(self.config['stories'])
        self.rejects = self.handle_rejects(self.config['rejects'])
    
    def handle_schema(self, raw_schema: dict) -> IntentNode:
        raw_root = raw_schema.get('root', None)
        if raw_root is None:
            warnings.warn('schema must have a root node as the beginning, otherwise intent recogition will not work')
            return None
    
        current_layers: list[tuple[dict, IntentNode | None]] = [(raw_root, None)]
        nodes: list[IntentNode] = []
        
        # 层次遍历
        while len(current_layers) > 0:
            new_current_layers: list[tuple[dict, IntentNode | None]] = []
            for raw_node, intent_node in current_layers:
                name = raw_node.get('name', None)
                children = raw_node.get('children', None)
                description = raw_node.get('description', None)
                if name is None:
                    raise NameError('you must specify a name in story item, current item : {}'.format(raw_node))
                if children is None:
                    children = []
                
                if name not in self.intent2id:
                    assign_id = len(self.intent2id)
                    self.intent2id[name] = assign_id
                    self.id2intent[assign_id] = name
                
                node = IntentNode(name, description, [], intent_node, [])
                self.name2node[name] = node

                nodes.append(node)
                if intent_node:
                    intent_node.children.append(node)
                for raw_node in children:
                    new_current_layers.append((raw_node, node))
            current_layers.clear()
            current_layers.extend(new_current_layers)
        return nodes[0]    
    
    def handle_stories(self, raw_stories: list[dict]) -> list[Story]:
        stories: list[Story] = []
        for pair in raw_stories:
            message = pair.get('message', None)
            intent = pair.get('intent', None)
            if intent not in self.intent2id:
                warnings.warn('{} is not the intent you declare in schema, so this pair will be ignored'.format(intent))
                continue
            if message and intent:
                story = Story(message, intent)
                node = self.name2node.get(intent)
                node.stories.append(story)
                stories.append(story)
        return stories
    
    def handle_rejects(self, raw_rejects: list[str]) -> list[str]:
        rejects = []
        for reject in raw_rejects:
            rejects.append(reject)
        return rejects
    
    def generate_chunk(self, stories: list[Story]) -> tuple[str]:
        prompts = []
        for story in stories:
            prompts.append('Message: ' + story.message.strip())
            intent_id = self.intent2id.get(story.intent)
            prompts.append('Intent: { id: %s }' % (intent_id))
            
        prompts.pop()
        
        user_content = '\n'.join(prompts) + '\n' + 'Intent: '
        assistant_content = '{id : %s}' % (intent_id)
        return user_content, assistant_content
    
    def generate_llm_message(self, question: str, intent: IntentNode = None, chunk_size: int = 5, max_chunk_num: int = 10):
        if intent is None:
            intent = self.schema
        
        story_cache = []
        for node in intent.children:
            story_cache.extend(node.stories)
        
        random.shuffle(story_cache)
        chunk_num = math.ceil(len(story_cache) / chunk_size)
        message = []
        for chunk_id in range(chunk_num):
            start = chunk_id * chunk_size
            end = min(len(story_cache), start + chunk_size)
            chunk = story_cache[start: end]
            user_content, assistant_content = self.generate_chunk(chunk)
            message.append({
                'role': 'user',
                'content': user_content
            })
            message.append({
                'role': 'assistant',
                'content': assistant_content
            })

            if len(message) / 2 >= max_chunk_num:
                break
        
        message.append({
            'role': 'user',
            'content': question + '\nIntent: '
        })

        # 创建开头的预设
        preset = 'Label a users message from a conversation with an intent. Reply ONLY with the name of the intent.'
        intent_preset = ['The intent should be one of the following:']
        for node in intent.children:
            intent_id = self.intent2id.get(node.name)
            intent_preset.append('- {}'.format(intent_id))
        intent_preset = '\n'.join(intent_preset)
        message[0]['content'] = preset + '\n' + intent_preset + '\n' + message[0]['content']
        return message
        

class KIntent:
    path: str
    engine: PromptEngine
    def __init__(self, path: str) -> None:
        self.path = path
        self.engine = PromptEngine(path)
    
    def inference(self, question: str, chunk_size: int = 5, max_chunk_num: int = 10) -> list[IntentNode]:
        root_node = self.engine.schema
        results: list[IntentNode] = []
        stack = [root_node]
        while len(stack) > 0:
            node = stack.pop()
            


if __name__ == '__main__':
    prompt_engine = PromptEngine('./story.yml')
    msg = prompt_engine.generate_llm_message('如何解决 digital ide 无法载入配置文件的问题？')
    print(msg)