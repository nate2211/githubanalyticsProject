# pipeline.py
from __future__ import annotations

import dataclasses
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Tuple, Callable


@dataclass
class BlockInstance:
    name: str
    params: Dict[str, Any]


@dataclass
class Pipeline:
    blocks: List[BlockInstance]

    def run(self, payload: Any, runner: Callable[[str, Any, Dict[str, Any]], Tuple[Any, Dict[str, Any]]]) -> Tuple[Any, Dict[str, Any]]:
        meta_all: Dict[str, Any] = {"steps": []}
        cur = payload
        for bi in self.blocks:
            out, meta = runner(bi.name, cur, bi.params)
            meta_all["steps"].append({"block": bi.name, "meta": meta})
            cur = out
        return cur, meta_all
