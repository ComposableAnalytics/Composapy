from enum import Enum
import json
from typing import List
import uuid

from composapy.decorators import session_required
from composapy.session import get_session
from composapy.utils import _urljoin, _read_static_resource

from CompAnalytics.IServices.Deploy import ResourceManager


class IDataSource(Enum):
    TABLE = "TABLE"
    QUERYVIEW = "QUERYVIEW"


class ITableResult:
    """HTML wrapper around a Table or Queryview result that enables interactive, server-side visualization via jQuery DataTables."""

    ASSET_SERVICE_NAME = "AssetService"
    JS_ASSET_SERVICE_ENDPOINT = "GetJavascript"
    CSS_ASSET_SERVICE_ENDPOINT = "GetStylesheet"
    QUERYVIEW_SERVICE_NAME = "QueryViewService"
    QUERYVIEW_ENDPOINT = "RunQueryDynamic"
    TABLE_SERVICE_NAME = "TableService"
    TABLE_ENDPOINT = "PostUiTableByTable"

    def __init__(
        self, data_columns: List[str], data_source: IDataSource, contract: any
    ):
        self.columns = data_columns
        self.src = data_source
        self.contract = contract
        self.template_params = {
            "TABLE_ID": "",
            "JS_ASSET_SERVICE_URI": "",
            "DATATABLES_CSS_URI": "",
            "DATA_SERVICE_URI": "",
            "REQUEST_ARGS": "",
            "COLUMN_NAMES": "",
            "DATA_SOURCE": "",
            "DEFAULT_PAGE_SIZE": "",
            "PAGE_NUMBER_DISPLAY": "",
        }

    @session_required
    def _set_template_values(self, html: str) -> str:
        session = get_session()
        mgr = session.resource_manager

        page_number_display_style = "unset"
        if self.src == IDataSource.TABLE:
            data_service_name = self.TABLE_SERVICE_NAME
            data_endpoint = self.TABLE_ENDPOINT
            request_args = self.contract
            default_page_size = 10
        elif self.src == IDataSource.QUERYVIEW:
            data_service_name = self.QUERYVIEW_SERVICE_NAME
            data_endpoint = self.QUERYVIEW_ENDPOINT
            request_args = {"queryView": self.contract}
            default_page_size = self.contract.PagingOptions.PageLimit
            if self.contract.PagingOptions.LimitPaging:
                page_number_display_style = "none"
        else:
            raise ITableException(
                f"Cannot create interactive table from data source '{self.src}'"
            )

        self.template_params["TABLE_ID"] = str(uuid.uuid4())
        self.template_params["JS_ASSET_SERVICE_URI"] = (
            self._create_service_endpoint_uri(
                mgr, self.ASSET_SERVICE_NAME, self.JS_ASSET_SERVICE_ENDPOINT
            )
        )
        self.template_params["DATATABLES_CSS_URI"] = _urljoin(
            session.uri, "scripts/vendor/DataTables/media/css/jquery.dataTables.css"
        )
        self.template_params["DATA_SERVICE_URI"] = self._create_service_endpoint_uri(
            mgr, data_service_name, data_endpoint
        )
        self.template_params["REQUEST_ARGS"] = json.dumps(request_args)
        self.template_params["COLUMN_NAMES"] = json.dumps(
            [{"title": col, "name": col} for col in self.columns]
        )
        self.template_params["DATA_SOURCE"] = self.src.value
        self.template_params["DEFAULT_PAGE_SIZE"] = str(default_page_size)
        self.template_params["PAGE_NUMBER_DISPLAY"] = page_number_display_style

        # inject values into template
        for key, value in self.template_params.items():
            html = html.replace(f"<#= {key} #>", value)

        return html

    def _create_service_endpoint_uri(
        self, mgr: ResourceManager, service: str, endpoint: str
    ) -> str:
        return _urljoin(str(mgr.CreateServiceEndpointUri(service)), endpoint)

    def _repr_html_(self) -> str:
        html_template = _read_static_resource(
            "datatables_template.html", decode_bytes=True
        )
        return self._set_template_values(html_template)


class ITableException(Exception):
    pass
