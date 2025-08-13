import hashlib
import json
from time import time
from typing import Dict, List, Optional

class Block:
    def __init__(self, index: int, timestamp: float, data: str, previous_hash: str):
        self.index = index
        self.timestamp = timestamp
        self.data = data
        self.previous_hash = previous_hash
        self.hash = self.calculate_hash()
    
    def calculate_hash(self) -> str:
        block_string = json.dumps({
            'index': self.index,
            'timestamp': self.timestamp,
            'data': self.data,
            'previous_hash': self.previous_hash
        }, sort_keys=True).encode()
        return hashlib.sha256(block_string).hexdigest()
class Blockchain:
    def __init__(self):
        self.chain = []
        self.create_genesis_block()
    
    def create_genesis_block(self):
        genesis_block = Block(0, time(), "Genesis Block", "0")
        self.chain.append(genesis_block)
    
    def get_latest_block(self):
        return self.chain[-1]
    
    def add_block(self, data):
        new_block = Block(
            index=len(self.chain),
            timestamp=time(),
            data=data,
            previous_hash=self.get_latest_block().hash
        )
        self.chain.append(new_block)
        return new_block.hash
    
    def is_chain_valid(self):
        for i in range(1, len(self.chain)):
            current_block = self.chain[i]
            previous_block = self.chain[i-1]
            
            if current_block.hash != current_block.calculate_hash():
                return False
            
            if current_block.previous_hash != previous_block.hash:
                return False
        
        return True
    
    def get_block_by_hash(self, block_hash):
        for block in self.chain:
            if block.hash == block_hash:
                return block
        return None
# class Blockchain:
#     def __init__(self):
#         self.chain: List[Block] = []
#         self.create_genesis_block()
    
#     def create_genesis_block(self):
#         genesis_block = Block(0, time(), "Genesis Block", "0")
#         self.chain.append(genesis_block)
    
#     def get_latest_block(self) -> Block:
#         return self.chain[-1]
    
#     def add_block(self, data: str) -> str:
#         new_block = Block(
#             index=len(self.chain),
#             timestamp=time(),
#             data=data,
#             previous_hash=self.get_latest_block().hash
#         )
#         self.chain.append(new_block)
#         return new_block.hash
    
#     def is_chain_valid(self) -> bool:
#         for i in range(1, len(self.chain)):
#             current_block = self.chain[i]
#             previous_block = self.chain[i-1]
            
#             if current_block.hash != current_block.calculate_hash():
#                 return False
            
#             if current_block.previous_hash != previous_block.hash:
#                 return False
        
#         return True
    
#     def get_block_by_hash(self, block_hash: str) -> Optional[Block]:
#         for block in self.chain:
#             if block.hash == block_hash:
#                 return block
#         return None