import transformers
import torch
from lm_eval.base import BaseLM

# TODO: this is hacky
import sys
parentpath = "/home/jc3464/QuantHerd/quant-balance-herd-smooth/"
print(f"adding parentpath {parentpath}")
sys.path.insert(1, str(parentpath))
from quantize.fake_quant import load_OPTQ_local

class HFLM(BaseLM):
    def __init__(
        self,
        device="cuda",
        pretrained="gpt2",
        revision="main",
        subfolder=None,
        tokenizer=None,
        batch_size=1,
        offload_folder="lm_offload",
        custom_load=False,
        custom_name="facebook/opt-125m",
        custom_a_bits=8,
    ):
        super().__init__()

        assert isinstance(device, str)
        assert isinstance(pretrained, str)
        assert isinstance(batch_size, int)

        # TODO update: moving to gpu handled in from_pretrained(device_map='auto')
        if device:
            if device not in ["cuda", "cpu"]:
                device = int(device)
            self._device = torch.device(device)
            print(f"Using device '{device}'")
        else:
            print("Device not specified")
            print(f"Cuda Available? {torch.cuda.is_available()}")
            self._device = (
                torch.device("cuda")
                if torch.cuda.is_available()
                else torch.device("cpu")
            )

        # TODO: update this to be less of a hack once subfolder is fixed in HF
        revision = revision + ("/" + subfolder if subfolder is not None else "")

        if custom_load:
            self.gpt2 = load_OPTQ_local(
                model_name=custom_name,
                load_path=pretrained,
                a_bits=custom_a_bits,
                dtype=torch.float16,
                device_map='auto',
                offload_folder=offload_folder,
                offload_state_dict=True,
            )
        else:
            self.gpt2 = transformers.AutoModelForCausalLM.from_pretrained(
                pretrained,
                revision=revision,
                # TODO: jerry update for LLM load
                use_auth_token="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",
                torch_dtype=torch.float16,
                device_map='auto',
                offload_folder=offload_folder,
                offload_state_dict=True,
            ) #.to(self.device)
        self.gpt2.eval()

        self.tokenizer = transformers.AutoTokenizer.from_pretrained(
            pretrained if tokenizer is None else tokenizer,
            revision=revision,
            use_auth_token="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",
        )

        assert isinstance(
            self.tokenizer,
            (
                transformers.GPT2Tokenizer,
                transformers.GPT2TokenizerFast,
                transformers.T5Tokenizer,
                transformers.T5TokenizerFast,
            ),
        ), "this tokenizer has not been checked for compatibility yet!"

        self.vocab_size = self.tokenizer.vocab_size

        # TODO: jerry update commenting this out, see https://github.com/EleutherAI/lm-evaluation-harness/issues/368
        # if isinstance(
        #     self.tokenizer, (transformers.GPT2Tokenizer, transformers.GPT2TokenizerFast)
        # ):
        #     assert self.tokenizer.encode("hello\n\nhello") == [
        #         31373,
        #         198,
        #         198,
        #         31373,
        #     ], self.tokenizer.encode("hello\n\nhello")

        # multithreading and batching
        self.batch_size_per_gpu = batch_size  # todo: adaptive batch size

        # TODO: fix multi-gpu
        # gpus = torch.cuda.device_count()
        # if gpus > 1:
        #     self.gpt2 = nn.DataParallel(self.gpt2)

    @property
    def eot_token_id(self):
        # we use EOT because end of *text* is more accurate for what we're doing than end of *sentence*
        return self.tokenizer.eos_token_id

    @property
    def max_length(self):
        try:
            return self.gpt2.config.n_ctx
        except AttributeError:
            # gptneoconfig doesn't have n_ctx apparently
            return self.gpt2.config.max_position_embeddings

    @property
    def max_gen_toks(self):
        return 256

    @property
    def batch_size(self):
        # TODO: fix multi-gpu
        return self.batch_size_per_gpu  # * gpus

    @property
    def device(self):
        # TODO: fix multi-gpu
        return self._device

    def tok_encode(self, string: str):
        return self.tokenizer.encode(string, add_special_tokens=False)

    def tok_decode(self, tokens):
        return self.tokenizer.decode(tokens)

    def _model_call(self, inps):
        """
        inps: a torch tensor of shape [batch, sequence]
        the size of sequence may vary from call to call

        returns: a torch tensor of shape [batch, sequence, vocab] with the
        logits returned from the model
        """
        with torch.no_grad():
            return self.gpt2(inps)[0][:, :, :50257]

    def _model_generate(self, context, max_length, eos_token_id):
        return self.gpt2.generate(
            context, max_length=max_length, eos_token_id=eos_token_id, do_sample=False
        )


# for backwards compatibility
GPT2LM = HFLM
