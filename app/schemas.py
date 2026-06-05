from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any
from datetime import datetime, date

# --- User Schemas ---
class UserBase(BaseModel):
    username: str
    email: str
    role: Optional[str] = "Reviewer"
    active: Optional[bool] = True

class UserCreate(UserBase):
    password: str

class UserLogin(BaseModel):
    email: str
    password: str

class User(UserBase):
    id: str
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True

class Token(BaseModel):
    access_token: str
    token_type: str

class TokenData(BaseModel):
    username: Optional[str] = None

# --- Organization Schemas ---
class OrganizationBase(BaseModel):
    name: str
    type: str = "Asset Manager"

class OrganizationCreate(OrganizationBase):
    id: str

class Organization(OrganizationBase):
    id: str
    created_at: datetime

    class Config:
        from_attributes = True

# --- Product Schemas ---
class ProductBase(BaseModel):
    name: str
    sfdr_article: str = "Article 8"
    strategy: Optional[str] = None
    benchmark: Optional[str] = None
    active: bool = True

class ProductCreate(ProductBase):
    id: str
    organization_id: str

class Product(ProductBase):
    id: str
    organization_id: str
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True

# --- Reporting Project Schemas ---
class ReportingProjectBase(BaseModel):
    name: str
    disclosure_type: str  # "entity_pai", "precontractual", "periodic"
    reporting_period_start: date
    reporting_period_end: date

class ReportingProjectCreate(ReportingProjectBase):
    product_id: Optional[str] = None
    organization_id: str = "default_org"

class ReportingProject(ReportingProjectBase):
    id: str
    organization_id: str
    product_id: Optional[str]
    status: str
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True

# --- Document Schemas ---
class DocumentBase(BaseModel):
    file_name: str
    file_type: str
    source_type: str

class Document(DocumentBase):
    id: str
    project_id: str
    storage_url: str
    parsed_status: str
    uploaded_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True

# --- Regulation Field Schemas ---
class RegulationFieldBase(BaseModel):
    framework: str = "SFDR"
    disclosure_type: str
    annex_code: Optional[str] = None
    field_code: str
    field_label: str
    field_kind: str
    mandatory: bool = True
    guidance: Optional[Dict[str, Any]] = None
    regulation_version: str = "2022/1288"

class RegulationField(RegulationFieldBase):
    id: str

    class Config:
        from_attributes = True

# --- Field Evidence Schemas ---
class FieldEvidenceBase(BaseModel):
    source_locator: Optional[Dict[str, Any]] = None
    extracted_value: Optional[Any] = None
    confidence: float
    extraction_method: str = "hybrid_retrieval"
    regulation_version: Optional[str] = None
    prompt_version: Optional[str] = None
    model_parameters: Optional[Dict[str, Any]] = None

class FieldEvidence(FieldEvidenceBase):
    id: str
    project_id: str
    regulation_field_id: str
    document_chunk_id: Optional[str]
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True

# --- Field Answer Schemas ---
class FieldAnswerBase(BaseModel):
    answer_json: Optional[Dict[str, Any]] = None
    answer_text: Optional[str] = None
    status: str = "Draft"

class FieldAnswerUpdate(BaseModel):
    answer_text: str
    status: str = "Draft"
    approved_by_user_id: Optional[str] = None  # review workflow user ID
    answer_json: Optional[Dict[str, Any]] = None

class FieldAnswer(FieldAnswerBase):
    id: str
    project_id: str
    regulation_field_id: str
    model_name: Optional[str]
    generated_at: datetime
    updated_at: datetime
    
    # Versioning
    version_no: int
    is_latest: bool
    regulation_version: Optional[str]
    prompt_version: Optional[str]
    model_parameters: Optional[Dict[str, Any]]
    
    approved_by: Optional[str]

    class Config:
        from_attributes = True

# --- Validation Result Schemas ---
class ValidationResult(BaseModel):
    id: str
    project_id: str
    regulation_field_id: Optional[str]
    rule_name: str
    severity: str
    passed: bool
    details: Optional[Dict[str, Any]] = None
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True

# --- UI Helper Matrix Schema ---
class MatrixItem(BaseModel):
    field_id: str
    field_code: str
    field_label: str
    field_kind: str
    mandatory: bool
    annex_code: Optional[str]
    description: Optional[str]
    expected_unit: Optional[str]
    regulation_version: str = "2022/1288"
    
    # Answers & Evidence (Optional if not run yet)
    answer_id: Optional[str] = None
    answer_text: Optional[str] = None
    answer_status: str = "Missing" # "Draft", "Approved", "Rejected", "Missing"
    version_no: int = 1
    is_latest: bool = True
    
    evidence_id: Optional[str] = None
    evidence_quote: Optional[str] = None
    extracted_value: Optional[Any] = None
    confidence: float = 0.0
    page_no: Optional[int] = None
    source_file: Optional[str] = None
    
    validation_passed: bool = True
    validation_errors: List[str] = []


# --- Audit Log Schema ---
class AuditLogResponse(BaseModel):
    id: str
    entity_type: str
    entity_id: str
    action: str
    actor_id: Optional[str] = None
    project_id: Optional[str] = None
    payload: Optional[Dict[str, Any]] = None
    created_at: datetime
    actor_username: Optional[str] = None
    actor_role: Optional[str] = None

    class Config:
        from_attributes = True
