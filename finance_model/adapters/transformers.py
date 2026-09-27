from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import torch
from transformers import AutoModelForCausalLM, AutoTokenizer


@dataclass(frozen=True, slots=True)
class Generation:
    text: str
    prompt_tokens: int
    completion_tokens: int
    model_id: str


class TransformersFinanceModel:
    """Local transformer inference adapter.

    Inference only: no broker, risk, portfolio mutation, or order access.
    """

    def __init__(
        self,
        model_id: str,
        *,
        device_map: str = "auto",
        torch_dtype: torch.dtype | None = None,
    ) -> None:
        self.model_id = model_id
        dtype = torch_dtype or (
            torch.bfloat16 if torch.cuda.is_available() else torch.float32
        )

        self.tokenizer = AutoTokenizer.from_pretrained(
            model_id,
            use_fast=True,
        )
        if self.tokenizer.pad_token is None:
            self.tokenizer.pad_token = self.tokenizer.eos_token

        kwargs: dict[str, Any] = {
            "device_map": device_map,
            "torch_dtype": dtype,
        }

        self.model = AutoModelForCausalLM.from_pretrained(
            model_id,
            **kwargs,
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
        if not prompt.strip():
            raise ValueError("prompt cannot be empty")
        if max_new_tokens <= 0:
            raise ValueError("max_new_tokens must be positive")

        inputs = self.tokenizer(
            prompt,
            return_tensors="pt",
        )
        device = next(self.model.parameters()).device
        inputs = {key: value.to(device) for key, value in inputs.items()}

        generation_kwargs: dict[str, Any] = {
            "max_new_tokens": max_new_tokens,
            "do_sample": temperature > 0.0,
            "top_p": top_p,
            "pad_token_id": self.tokenizer.pad_token_id,
        }
        if temperature > 0.0:
            generation_kwargs["temperature"] = temperature

        output = self.model.generate(
            **inputs,
            **generation_kwargs,
        )

        prompt_len = int(inputs["input_ids"].shape[-1])
        generated = output[0][prompt_len:]
        text = self.tokenizer.decode(
            generated,
            skip_special_tokens=True,
        )

        return Generation(
            text=text,
            prompt_tokens=prompt_len,
            completion_tokens=int(generated.shape[-1]),
            model_id=self.model_id,
        )
