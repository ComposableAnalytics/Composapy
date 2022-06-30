import numpy as np
import pandas as pd

from composapy.api import ComposableApi
from composapy.patch.table import (
    _make_pandas_dtypes_from_list_of_column_defs,
    MAP_CS_TYPES_TO_PANDAS_TYPES,
)
from composapy.session import get_session
from composapy.stream import CsStream

# from CompAnalytics.IServices import *


class QueryView(ComposableApi):
    """A wrapper class for dataflow operations."""

    def get_queryview(self, id: int) -> pd.DataFrame:
        session = get_session()

        queryview_service = session.services["QueryViewService"]
        queryview = queryview_service.Get(id)
        queryview_data = queryview_service.RunQueryDynamic(queryview)
        column_names = []
        for column in queryview_data.ColumnDefinitions:
            column_names.append(column.Name)

        df = pd.DataFrame(queryview_data.Data)
        df.columns = column_names
        dtypes_dict = _make_pandas_dtypes_from_list_of_column_defs(
            queryview_data.ColumnDefinitions
        )

        ## There is a pandas bug about converting objects to nullable ints, first need to convert to floats
        df.replace(to_replace=[None, "None"], value=np.nan, inplace=True)
        interim_dtypes = dtypes_dict.copy()
        for key in interim_dtypes.keys():
            if interim_dtypes[key] == "Int64":
                interim_dtypes[key] = "float"
        df = df.astype(interim_dtypes)
        return df.astype(dtypes_dict)

    def queryview_from_id_direct(self, queryview_id: int) -> pd.DataFrame:
        """
        Read a queryview from id to a pandas dataframe

        Parameters
        (int) id: queryview id.

        Return
        (pd.DataFrame) df: DataFrame of Queryview.
        """
        session = get_session()

        queryview = session.services["QueryViewService"].Get(queryview_id)
        queryview_data = session.services["QueryViewService"].RunQueryDynamic(queryview)
        columns_definitions = queryview_data.ColumnDefinitions
        column_names = []
        column_dtypes = {}

        for column_definition in columns_definitions:
            if not column_definition.Exclude:
                column_names.append(column_definition.Name)
                column_dtypes[column_definition.Name] = MAP_CS_TYPES_TO_PANDAS_TYPES[
                    column_definition.Type
                ]

        data = queryview_data.Data
        df = pd.DataFrame(data)
        df.columns = column_names
        # print(column_dtypes
        print(df.head())
        print(column_dtypes)
        return df.astype(column_dtypes)

    def queryview_from_id(self, queryview_id: int) -> pd.DataFrame:
        """
        Read a queryview from id to a pandas dataframe

        Parameters
        (int) id: queryview id.

        Return
        (pd.DataFrame) df: DataFrame of Queryview.
        """
        session = get_session()

        queryview = session.services["QueryViewService"].Get(queryview_id)
        paging_options = queryview.PagingOptions
        # print(paging_options.PageNum)
        # print(paging_options.PageLimit)
        paging_options.PageNum = 1
        paging_options.PageLimit = 0x7FFFFFFF
        queryview.PagingOptions = paging_options
        stream = session.services["QueryViewService"].GetQueryResultsDownloadWeb(
            queryview, "csv"
        )
        df = pd.read_csv(CsStream(stream))

        ## convert datetime by regex
        mask = df.astype(str).apply(
            lambda x: x.str.match(r"(\d{2,4}-\d{2}-\d{2,4})+").all()
        )
        df.loc[:, mask] = df.loc[:, mask].apply(pd.to_datetime)

        return df
