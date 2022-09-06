from System import TimeSpan
from System.ServiceModel import WebHttpBinding


def configure_binding(service_name: str, binding: WebHttpBinding) -> WebHttpBinding:
    if service_name in _service_binding_configs.keys():
        binding = _service_binding_configs[service_name](binding)
    return binding


def query_view_binding(binding: WebHttpBinding):
    binding.OpenTimeout = TimeSpan.MaxValue
    binding.CloseTimeout = TimeSpan.MaxValue
    binding.SendTimeout = TimeSpan.MaxValue
    binding.ReceiveTimeout = TimeSpan.MaxValue
    return binding


def data_flow_binding(binding: WebHttpBinding):
    binding.OpenTimeout = TimeSpan.MaxValue
    binding.CloseTimeout = TimeSpan.MaxValue
    binding.SendTimeout = TimeSpan.MaxValue
    binding.ReceiveTimeout = TimeSpan.MaxValue
    return binding


_service_binding_configs = {
    "QueryViewService": query_view_binding,
    "ApplicationService": data_flow_binding,
}
