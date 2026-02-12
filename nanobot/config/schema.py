"""Configuration schema using Pydantic."""

from pathlib import Path
from pydantic import BaseModel, Field
from pydantic_settings import BaseSettings


class WhatsAppConfig(BaseModel):
    """WhatsApp channel: private chats only. We never respond in groups."""
    enabled: bool = False
    bridge_url: str = "ws://localhost:3001"
    allow_from: list[str] = Field(default_factory=list)  # Allowed phone numbers (chats only)


class ChannelsConfig(BaseModel):
    """Configuration for chat channels (WhatsApp only; chats, never groups)."""
    whatsapp: WhatsAppConfig = Field(default_factory=WhatsAppConfig)


class AgentDefaults(BaseModel):
    """Default agent configuration. Por defeito: DeepSeek (agente) + Xiaomi MiMo (scope/heartbeat), APIs diretas."""
    workspace: str = "~/.nanobot/workspace"
    model: str = "deepseek/deepseek-chat"
    scope_model: str | None = "xiaomi_mimo/mimo-v2-flash"  # scope + heartbeat; APIs diretas Xiaomi
    max_tokens: int = 8192
    temperature: float = 0.7
    max_tool_iterations: int = 20


class AgentsConfig(BaseModel):
    """Agent configuration."""
    defaults: AgentDefaults = Field(default_factory=AgentDefaults)


class ProviderConfig(BaseModel):
    """LLM provider configuration."""
    api_key: str = ""
    api_base: str | None = None
    extra_headers: dict[str, str] | None = None  # Custom headers (e.g. APP-Code for AiHubMix)


class ProvidersConfig(BaseModel):
    """Configuration for LLM providers."""
    anthropic: ProviderConfig = Field(default_factory=ProviderConfig)
    openai: ProviderConfig = Field(default_factory=ProviderConfig)
    openrouter: ProviderConfig = Field(default_factory=ProviderConfig)
    deepseek: ProviderConfig = Field(default_factory=ProviderConfig)
    groq: ProviderConfig = Field(default_factory=ProviderConfig)
    zhipu: ProviderConfig = Field(default_factory=ProviderConfig)
    dashscope: ProviderConfig = Field(default_factory=ProviderConfig)  # 阿里云通义千问
    vllm: ProviderConfig = Field(default_factory=ProviderConfig)
    gemini: ProviderConfig = Field(default_factory=ProviderConfig)
    moonshot: ProviderConfig = Field(default_factory=ProviderConfig)
    aihubmix: ProviderConfig = Field(default_factory=ProviderConfig)  # AiHubMix API gateway
    xiaomi: ProviderConfig = Field(default_factory=ProviderConfig)  # Xiaomi MiMo (scope + heartbeat)
    perplexity: ProviderConfig = Field(default_factory=ProviderConfig)  # Perplexity Search API


class GatewayConfig(BaseModel):
    """Gateway/server configuration."""
    host: str = "0.0.0.0"
    port: int = 18790


class ToolsConfig(BaseModel):
    """Tools configuration (reserved for future use)."""
    pass


class Config(BaseSettings):
    """Root configuration for nanobot."""
    agents: AgentsConfig = Field(default_factory=AgentsConfig)
    channels: ChannelsConfig = Field(default_factory=ChannelsConfig)
    providers: ProvidersConfig = Field(default_factory=ProvidersConfig)
    gateway: GatewayConfig = Field(default_factory=GatewayConfig)
    tools: ToolsConfig = Field(default_factory=ToolsConfig)
    
    @property
    def workspace_path(self) -> Path:
        """Get expanded workspace path."""
        return Path(self.agents.defaults.workspace).expanduser()
    
    # Default base URLs for API gateways
    _GATEWAY_DEFAULTS = {"openrouter": "https://openrouter.ai/api/v1", "aihubmix": "https://aihubmix.com/v1"}

    def get_provider(self, model: str | None = None) -> ProviderConfig | None:
        """Get matched provider config (api_key, api_base, extra_headers). Falls back to first available."""
        model = (model or self.agents.defaults.model).lower()
        p = self.providers
        # Keyword → provider mapping (order matters: gateways first)
        keyword_map = {
            "aihubmix": p.aihubmix, "openrouter": p.openrouter,
            "deepseek": p.deepseek, "anthropic": p.anthropic, "claude": p.anthropic,
            "openai": p.openai, "gpt": p.openai, "gemini": p.gemini,
            "zhipu": p.zhipu, "glm": p.zhipu, "zai": p.zhipu,
            "dashscope": p.dashscope, "qwen": p.dashscope,
            "groq": p.groq, "moonshot": p.moonshot, "kimi": p.moonshot, "vllm": p.vllm,
            "xiaomi": p.xiaomi, "mimo": p.xiaomi,
        }
        for kw, provider in keyword_map.items():
            if kw in model:
                if (provider.api_key or "").strip():
                    return provider
                # Matched provider has no api_key; fall through to fallback
                break
        # Fallback: gateways first (can serve any model), then specific providers
        all_providers = [p.openrouter, p.aihubmix, p.anthropic, p.openai, p.deepseek,
                         p.gemini, p.zhipu, p.dashscope, p.moonshot, p.vllm, p.groq, p.xiaomi]
        p = next((pr for pr in all_providers if (pr.api_key or "").strip()), None)
        # Defensive: never return a provider with empty api_key
        return p if (p and (p.api_key or "").strip()) else None

    def get_api_key(self, model: str | None = None) -> str | None:
        """Get API key for the given model. Falls back to first available key."""
        p = self.get_provider(model)
        return p.api_key if p else None
    
    def get_api_base(self, model: str | None = None) -> str | None:
        """Get API base URL for the given model. Applies default URLs for known gateways."""
        p = self.get_provider(model)
        if p and p.api_base:
            return p.api_base
        # Default URLs for known gateways (openrouter, aihubmix)
        for name, url in self._GATEWAY_DEFAULTS.items():
            if p == getattr(self.providers, name):
                return url
        return None
    
    class Config:
        env_prefix = "NANOBOT_"
        env_nested_delimiter = "__"
