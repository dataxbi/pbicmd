from enum import Enum


class DataType(Enum):
    """Este enum es una copia del enum DataType definido en la librería .NET Microsoft.AnalysisServices.Tabular
    https://learn.microsoft.com/en-us/dotnet/api/microsoft.analysisservices.tabular.datatype?view=analysisservices-dotnet
    """

    AUTOMATIC = 1  # Internal only.
    BINARY = 17
    BOOLEAN = 11
    DATE_TIME = 9
    DECIMAL = 10
    DOUBLE = 8
    INT64 = 6
    STRING = 2
    UNKNOWN = 19  # Initial value of a newly created column, replaced with an actual value after saving a Column to the Server.
    VARIANT = 20  # A measure with varying data type.


class ColumnType(Enum):
    """Este enum es una copia del enum ColumnType definido en la librería .NET Microsoft.AnalysisServices.Tabular
    https://learn.microsoft.com/en-us/dotnet/api/microsoft.analysisservices.tabular.columntype?view=analysisservices-dotnet
    """

    CALCULATED = 2  # The contents of this column are computed by using an expression after the Data columns have been populated.
    CALCULATED_TABLE_COLUMN = 4  # The column exists in a calculated table, where the table and its columns are based on a calculated expression.
    DATA = 1  # The contents of this column come from a DataSource.
    ROW_NUMBER = 3  # This column is automatically added by the Server to every table.


class RelationshipEndCardinality(Enum):
    """Este enum es una copia del enum RelationshipEndCardinality definido en la librería .NET Microsoft.AnalysisServices.Tabular
    https://learn.microsoft.com/en-us/dotnet/api/microsoft.analysisservices.tabular.relationshipendcardinality?view=analysisservices-dotnet
    """

    MANY = 2  # Specifies the 'many' side of a one-to-many relationship.
    NONE = 0  # The relationship is unspecified.
    ONE = 1  # Specifies the 'one' side of a one-to-one or one-to-many relationship.


class CrossFilteringBehavior(Enum):
    """Este enum es una copia del enum CrossFilteringBehavior definido en la librería .NET Microsoft.AnalysisServices.Tabular
    https://learn.microsoft.com/en-us/dotnet/api/microsoft.analysisservices.tabular.crossfilteringbehavior?view=analysisservices-dotnet
    """

    AUTOMATIC = 3  # The engine will analyze the relationships and choose one of the behaviors by using heuristics.
    BOTHDIRECTIONS = 2  # Filters on either end of the relationship will automatically filter the other table.
    ONEDIRECTION = 1  # The rows selected in the 'To' end of the relationship will automatically filter scans of the table in the 'From' end of the relationship.


class AggregateFunction(Enum):
    """Este enum es una copia del enum AggregateFunction definido en la librería .NET Microsoft.AnalysisServices.Tabular
    https://learn.microsoft.com/en-us/dotnet/api/microsoft.analysisservices.tabular.aggregatefunction?view=analysisservices-dotnet
    """

    AVERAGE = 7  # Calculates the average of values for all non-empty child members.
    COUNT = 6  # Returns the rows count in the table.
    DEFAULT = 1  # The default aggregation is Sum for numeric columns. Otherwise the default is None.
    DISTINCTCOUNT = 8  # Returns the count of all unique child members.
    MAX = 5  # Returns the highest value for all child members.
    MIN = 4  # Returns the lowest value for all child members.
    NONE = 2  # Leaves the aggregate function unspecified.
    SUM = 3  # Calculates the sum of values contained in the column. This is the default aggregation function.
