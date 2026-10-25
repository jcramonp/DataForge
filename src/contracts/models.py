"""Foundational models for the generic configuration contract."""

from enum import Enum
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator


class StrictModel(BaseModel):
    model_config = ConfigDict(
        extra="forbid",
        str_strip_whitespace=True,
        populate_by_name=True,
    )


class SourceType(str, Enum):
    FILE = "file"
    POSTGRESQL = "postgresql"
    REST = "rest"


class RestPaginationStrategy(str, Enum):
    NONE = "none"
    PAGE = "page"
    OFFSET = "offset"


class FileFormat(str, Enum):
    CSV = "csv"
    JSON = "json"
    PARQUET = "parquet"


class DataType(str, Enum):
    STRING = "string"
    INTEGER = "integer"
    FLOAT = "float"
    BOOLEAN = "boolean"
    DATE = "date"
    DATETIME = "datetime"
    JSON = "json"


class Classification(str, Enum):
    PUBLIC = "public"
    INTERNAL = "internal"
    CONFIDENTIAL = "confidential"
    RESTRICTED = "restricted"


class Severity(str, Enum):
    WARNING = "warning"
    CRITICAL = "critical"


class TransformationOperation(str, Enum):
    CAST = "cast"
    TRIM = "trim"
    LOWER = "lower"
    UPPER = "upper"
    RENAME = "rename"


class QualityRuleType(str, Enum):
    NOT_NULL = "not_null"
    UNIQUE = "unique"
    GREATER_THAN = "greater_than"
    GREATER_THAN_OR_EQUAL = "greater_than_or_equal"
    LESS_THAN = "less_than"
    LESS_THAN_OR_EQUAL = "less_than_or_equal"
    BETWEEN = "between"
    ALLOWED_VALUES = "allowed_values"
    REGEX = "regex"


class GoldOperation(str, Enum):
    SELECT = "select"
    DROP = "drop"
    RENAME = "rename"
    FILTER = "filter"
    JOIN = "join"
    DERIVE = "derive"
    GROUP_BY = "group_by"
    AGGREGATE = "aggregate"


class FilterOperator(str, Enum):
    EQUAL = "eq"
    NOT_EQUAL = "ne"
    GREATER_THAN = "gt"
    GREATER_THAN_OR_EQUAL = "ge"
    LESS_THAN = "lt"
    LESS_THAN_OR_EQUAL = "le"
    IN = "in"
    NOT_IN = "not_in"


class JoinHow(str, Enum):
    INNER = "inner"
    LEFT = "left"
    RIGHT = "right"
    OUTER = "outer"


class DerivedOperation(str, Enum):
    ADD = "add"
    SUBTRACT = "subtract"
    MULTIPLY = "multiply"
    DIVIDE = "divide"


class AggregationFunction(str, Enum):
    SUM = "sum"
    AVG = "avg"
    MIN = "min"
    MAX = "max"
    COUNT = "count"
    NUNIQUE = "nunique"


class ClientConfig(StrictModel):
    code: str = Field(min_length=1)
    name: str = Field(min_length=1)
    description: str | None = None


class ProjectConfig(StrictModel):
    code: str = Field(min_length=1)
    name: str = Field(min_length=1)
    description: str | None = None


class SourceConfig(StrictModel):
    """Source identity and connection reference."""

    code: str = Field(min_length=1)
    name: str = Field(min_length=1)
    type: SourceType
    connection_reference: str | None = Field(default=None, min_length=1)
    description: str | None = None


class RestPaginationConfig(StrictModel):
    """Supported REST pagination strategies."""

    strategy: RestPaginationStrategy = RestPaginationStrategy.NONE

    page_param: str = "page"
    page_size_param: str = "page_size"
    page_size: int = Field(default=100, ge=1)
    start_page: int = Field(default=1, ge=0)

    offset_param: str = "offset"
    limit_param: str = "limit"
    start_offset: int = Field(default=0, ge=0)

    max_pages: int = Field(default=100, ge=1)


class SourceObjectConfig(StrictModel):
    """Physical object inside a configured source."""

    # File
    path: str | None = Field(default=None, min_length=1)
    format: FileFormat | None = None

    # PostgreSQL
    schema_name: str | None = Field(
        default=None,
        alias="schema",
        min_length=1,
    )
    table: str | None = Field(default=None, min_length=1)
    query: str | None = Field(default=None, min_length=1)

    # REST
    endpoint: str | None = Field(default=None, min_length=1)
    method: Literal["GET"] = "GET"

    params: dict[str, Any] = Field(default_factory=dict)
    headers: dict[str, str] = Field(default_factory=dict)

    timeout_seconds: float = Field(
        default=30.0,
        gt=0,
        le=300,
    )

    records_path: str | None = Field(default=None, min_length=1)

    pagination: RestPaginationConfig = Field(
        default_factory=RestPaginationConfig
    )

    @model_validator(mode="after")
    def validate_location(self) -> "SourceObjectConfig":
        if not any([
            self.path,
            self.table,
            self.query,
            self.endpoint,
        ]):
            raise ValueError(
                "A source object must define at least one of: "
                "'path', 'table', 'query', or 'endpoint'"
            )

        return self


class DatasetReferenceConfig(StrictModel):
    dataset: str = Field(min_length=1)
    columns: list[str] = Field(min_length=1)


class ForeignKeyConfig(StrictModel):
    columns: list[str] = Field(min_length=1)
    references: DatasetReferenceConfig

    @model_validator(mode="after")
    def validate_column_count(self) -> "ForeignKeyConfig":
        if len(self.columns) != len(self.references.columns):
            raise ValueError(
                "Foreign-key columns and referenced columns "
                "must have the same length"
            )

        return self


class DatasetKeysConfig(StrictModel):
    primary: list[str] = Field(default_factory=list)
    foreign: list[ForeignKeyConfig] = Field(default_factory=list)


class TransformationConfig(StrictModel):
    operation: TransformationOperation

    column: str | None = Field(default=None, min_length=1)

    target_type: DataType | None = Field(
        default=None,
        alias="type",
    )

    from_column: str | None = Field(
        default=None,
        alias="from",
        min_length=1,
    )

    to_column: str | None = Field(
        default=None,
        alias="to",
        min_length=1,
    )

    @model_validator(mode="after")
    def validate_operation_parameters(self) -> "TransformationConfig":
        if self.operation == TransformationOperation.CAST:
            if self.column is None or self.target_type is None:
                raise ValueError(
                    "'cast' requires 'column' and 'type'"
                )

        elif self.operation in {
            TransformationOperation.TRIM,
            TransformationOperation.LOWER,
            TransformationOperation.UPPER,
        }:
            if self.column is None:
                raise ValueError(
                    f"'{self.operation.value}' requires 'column'"
                )

        elif self.operation == TransformationOperation.RENAME:
            if self.from_column is None or self.to_column is None:
                raise ValueError(
                    "'rename' requires 'from' and 'to'"
                )

        return self


class ColumnConfig(StrictModel):
    name: str = Field(min_length=1)
    type: DataType
    nullable: bool = True
    description: str | None = None
    classification: Classification = Classification.INTERNAL


class QualityRuleConfig(StrictModel):
    name: str = Field(min_length=1)
    rule: QualityRuleType
    column: str = Field(min_length=1)

    severity: Severity = Severity.CRITICAL
    mostly: float = Field(default=1.0, ge=0.0, le=1.0)
    allow_null: bool = True

    value: Any | None = None

    min_value: Any | None = None
    max_value: Any | None = None

    values: list[Any] | None = None
    pattern: str | None = None

    @model_validator(mode="after")
    def validate_rule_parameters(self) -> "QualityRuleConfig":
        comparison_rules = {
            QualityRuleType.GREATER_THAN,
            QualityRuleType.GREATER_THAN_OR_EQUAL,
            QualityRuleType.LESS_THAN,
            QualityRuleType.LESS_THAN_OR_EQUAL,
        }

        if self.rule in comparison_rules and self.value is None:
            raise ValueError(
                f"'{self.rule.value}' requires 'value'"
            )

        if self.rule == QualityRuleType.BETWEEN:
            if self.min_value is None or self.max_value is None:
                raise ValueError(
                    "'between' requires 'min_value' and 'max_value'"
                )

        if self.rule == QualityRuleType.ALLOWED_VALUES:
            if not self.values:
                raise ValueError(
                    "'allowed_values' requires a non-empty 'values' list"
                )

        if self.rule == QualityRuleType.REGEX:
            if not self.pattern:
                raise ValueError(
                    "'regex' requires 'pattern'"
                )

        return self


class AggregationConfig(StrictModel):
    column: str = Field(min_length=1)
    function: AggregationFunction
    alias: str = Field(min_length=1)


class GoldStepConfig(StrictModel):
    operation: GoldOperation

    columns: list[str] | None = None
    column: str | None = Field(default=None, min_length=1)

    from_column: str | None = Field(
        default=None,
        alias="from",
        min_length=1,
    )

    to_column: str | None = Field(
        default=None,
        alias="to",
        min_length=1,
    )

    operator: FilterOperator | None = None
    value: Any | None = None

    right_dataset: str | None = Field(default=None, min_length=1)
    left_on: list[str] | None = None
    right_on: list[str] | None = None
    how: JoinHow = JoinHow.INNER

    derived_operation: DerivedOperation | None = None
    operands: list[str] | None = None
    output_column: str | None = Field(default=None, min_length=1)

    aggregations: list[AggregationConfig] | None = None

    @model_validator(mode="after")
    def validate_gold_step(self) -> "GoldStepConfig":
        if self.operation in {
            GoldOperation.SELECT,
            GoldOperation.DROP,
            GoldOperation.GROUP_BY,
        }:
            if not self.columns:
                raise ValueError(
                    f"'{self.operation.value}' requires a non-empty 'columns' list"
                )

        elif self.operation == GoldOperation.RENAME:
            if self.from_column is None or self.to_column is None:
                raise ValueError(
                    "'rename' requires 'from' and 'to'"
                )

        elif self.operation == GoldOperation.FILTER:
            if (
                self.column is None
                or self.operator is None
                or self.value is None
            ):
                raise ValueError(
                    "'filter' requires 'column', 'operator' and 'value'"
                )

        elif self.operation == GoldOperation.JOIN:
            if (
                self.right_dataset is None
                or not self.left_on
                or not self.right_on
            ):
                raise ValueError(
                    "'join' requires 'right_dataset', "
                    "'left_on' and 'right_on'"
                )

            if len(self.left_on) != len(self.right_on):
                raise ValueError(
                    "'left_on' and 'right_on' must have the same length"
                )

        elif self.operation == GoldOperation.DERIVE:
            if (
                self.derived_operation is None
                or not self.operands
                or self.output_column is None
            ):
                raise ValueError(
                    "'derive' requires 'derived_operation', "
                    "'operands' and 'output_column'"
                )

            if len(self.operands) < 2:
                raise ValueError(
                    "'derive' requires at least two operands"
                )

        elif self.operation == GoldOperation.AGGREGATE:
            if not self.aggregations:
                raise ValueError(
                    "'aggregate' requires a non-empty "
                    "'aggregations' list"
                )

        return self


class GoldConfig(StrictModel):
    code: str = Field(min_length=1)
    name: str = Field(min_length=1)

    base_dataset: str = Field(min_length=1)

    enabled: bool = True

    plan: list[GoldStepConfig] = Field(
        default_factory=list
    )


class SilverConfig(StrictModel):
    transformations: list[TransformationConfig] = Field(default_factory=list)


class QualityConfig(StrictModel):
    rules: list[QualityRuleConfig] = Field(default_factory=list)


class DatasetConfig(StrictModel):
    """Logical dataset processed by DataForge."""

    code: str = Field(min_length=1)
    name: str = Field(min_length=1)

    source_object: SourceObjectConfig

    owner: str | None = Field(default=None, min_length=1)
    classification: Classification = Classification.INTERNAL
    description: str | None = None

    schema_: list[ColumnConfig] = Field(
        alias="schema",
        min_length=1,
    )

    keys: DatasetKeysConfig = Field(
        default_factory=DatasetKeysConfig
    )

    silver: SilverConfig = Field(
        default_factory=SilverConfig
    )

    quality: QualityConfig = Field(
        default_factory=QualityConfig
    )

    @model_validator(mode="after")
    def validate_dataset(self) -> "DatasetConfig":
        column_names = [column.name for column in self.schema_]

        if len(column_names) != len(set(column_names)):
            raise ValueError(
                "Dataset schema contains duplicate column names"
            )

        for column in self.keys.primary:
            if column not in column_names:
                raise ValueError(
                    f"Primary-key column '{column}' "
                    "does not exist in dataset schema"
                )

        for foreign_key in self.keys.foreign:
            for column in foreign_key.columns:
                if column not in column_names:
                    raise ValueError(
                        f"Foreign-key column '{column}' "
                        "does not exist in dataset schema"
                    )

        for rule in self.quality.rules:
            if rule.column not in column_names:
                raise ValueError(
                    f"Quality rule '{rule.name}' references "
                    f"unknown column '{rule.column}'"
                )

        for transformation in self.silver.transformations:
            if transformation.operation in {
                TransformationOperation.CAST,
                TransformationOperation.TRIM,
                TransformationOperation.LOWER,
                TransformationOperation.UPPER,
            }:
                if transformation.column not in column_names:
                    raise ValueError(
                        f"Transformation "
                        f"'{transformation.operation.value}' "
                        f"references unknown column "
                        f"'{transformation.column}'"
                    )

            elif transformation.operation == TransformationOperation.RENAME:
                if transformation.to_column not in column_names:
                    raise ValueError(
                        f"Rename target "
                        f"'{transformation.to_column}' "
                        "does not exist in normalized schema"
                    )

        return self


class DataForgeContract(StrictModel):
    """Root configuration contract for one DataForge project/source."""

    contract_version: Literal["1.0"] = "1.0"

    client: ClientConfig
    project: ProjectConfig
    source: SourceConfig

    datasets: list[DatasetConfig] = Field(min_length=1)

    gold: list[GoldConfig] = Field(default_factory=list)

    @model_validator(mode="after")
    def validate_contract(self) -> "DataForgeContract":
        dataset_codes = [
            dataset.code
            for dataset in self.datasets
        ]

        if len(dataset_codes) != len(set(dataset_codes)):
            raise ValueError(
                "Dataset codes must be unique within a contract"
            )

        datasets_by_code = {
            dataset.code: dataset
            for dataset in self.datasets
        }

        # Validate source-object shape according to source type.
        for dataset in self.datasets:
            obj = dataset.source_object

            if self.source.type == SourceType.FILE:
                if obj.path is None:
                    raise ValueError(
                        f"File dataset '{dataset.code}' "
                        "requires source_object.path"
                    )

                if obj.format is None:
                    raise ValueError(
                        f"File dataset '{dataset.code}' "
                        "requires source_object.format"
                    )

            elif self.source.type == SourceType.POSTGRESQL:
                if obj.table is None and obj.query is None:
                    raise ValueError(
                        f"PostgreSQL dataset '{dataset.code}' requires "
                        "source_object.table or source_object.query"
                    )

            elif self.source.type == SourceType.REST:
                if obj.endpoint is None:
                    raise ValueError(
                        f"REST dataset '{dataset.code}' "
                        "requires source_object.endpoint"
                    )

        # Validate cross-dataset foreign keys.
        for dataset in self.datasets:
            for foreign_key in dataset.keys.foreign:
                reference = foreign_key.references

                if reference.dataset not in datasets_by_code:
                    raise ValueError(
                        f"Dataset '{dataset.code}' references "
                        f"unknown dataset '{reference.dataset}'"
                    )

                referenced_dataset = datasets_by_code[
                    reference.dataset
                ]

                referenced_columns = {
                    column.name
                    for column in referenced_dataset.schema_
                }

                for column in reference.columns:
                    if column not in referenced_columns:
                        raise ValueError(
                            f"Foreign key from dataset "
                            f"'{dataset.code}' references unknown "
                            f"column '{column}' in dataset "
                            f"'{reference.dataset}'"
                        )

        gold_codes = [gold.code for gold in self.gold]

        if len(gold_codes) != len(set(gold_codes)):
            raise ValueError(
                "Gold dataset codes must be unique"
            )

        for gold in self.gold:
            if gold.base_dataset not in datasets_by_code:
                raise ValueError(
                    f"Gold dataset '{gold.code}' uses unknown "
                    f"base dataset '{gold.base_dataset}'"
                )

            for step in gold.plan:
                if step.operation == GoldOperation.JOIN:
                    if step.right_dataset not in datasets_by_code:
                        raise ValueError(
                            f"Gold dataset '{gold.code}' joins "
                            f"unknown dataset "
                            f"'{step.right_dataset}'"
                        )


        return self
