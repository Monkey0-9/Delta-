from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import torch
from transformers import (
    AutoModelForCausalLM,
    AutoTokenizer,
)


@dataclass(frozen=True, slots=True)
class Generation:
    text: str
    prompt_tokens: int
    completion_tokens: int


class TransformersFinanceModel:
    """
    DELTA finance-model adapter.

    This layer owns model inference only.
    It does not own:
      - broker access
      - risk authorization
      - order submission
      - portfolio mutation
    """

    def __init__(
        self,
        model_id: str,
        *,
        device_map: str = "auto",
        torch_dtype: torch.dtype = torch.bfloat16,
    ) -> None:
        self.model_id = model_id

        self.tokenizer = AutoTokenizer.from_pretrained(
            model_id,
            use_fast=True,
        )

        if self.tokenizer.pad_token is None:
            self.tokenizer.pad_token = self.tokenizer.eos_token

        self.model = AutoModelForCausalLM.from_pretrained(
            model_id,
            device_map=device_map,
            torch_dtype=torch_dtype,
        )

        self.model.eval()

    @torch.inference_mode()
    def generate(
        self,
        prompt: str,
        *,
        max_new_tokens: int = 256,
        temperature: float = 0.0,
        top_p: float = 1.0,
    ) -> Generation:
        inputs = self.tokenizer(
            prompt,
            return_tensors="pt",
        )

        inputs = {
            key: value.to(self.model.device)
            for key, value in inputs.items()
        }

        output = self.model.generate(
            **inputs,
            max_new_tokens=max_new_tokens,
            do_sample=temperature > 0.0,
            temperature=temperature if temperature > 0.0 else None,
            top_p=top_p,
            pad_token_id=self.tokenizer.pad_token_id,
        )

        generated = output[0][inputs["input_ids"].shape[-1]:]

        text = self.tokenizer.decode(
            generated,
            skip_special_tokens=True,
        )

        return Generation(
            text=text,
            prompt_tokens=int(inputs["input_ids"].shape[-1]),
            completion_tokens=int(generated.shape[-1]),
        )