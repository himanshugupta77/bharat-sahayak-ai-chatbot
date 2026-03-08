"""Eligibility route handler for FastAPI."""

import os
import sys
import operator
import re
from typing import Any, Dict, List, Tuple, Callable, Optional

from fastapi import APIRouter, Request, status
from fastapi.responses import JSONResponse

# Add shared module to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from shared.models import (
    EligibilityRequest,
    EligibilityResponse,
    EligibilityCriterion,
    EligibilityExplanation,
    SchemeDetails
)
from shared.utils import (
    get_dynamodb_table,
    validate_scheme_id,
    get_current_timestamp,
    logger
)
from shared.data_privacy import (
    anonymize_user_info,
    validate_data_minimization,
    log_data_access
)

# Create router
router = APIRouter()


class EligibilityRule:
    """
    Represents a single eligibility rule with safe evaluation.
    
    This class encapsulates an eligibility criterion and provides
    safe evaluation without using eval() or exec().
    """
    
    def __init__(self, criterion: str, rule_type: str, requirement: str, evaluator_str: str):
        """
        Initialize an eligibility rule.
        
        Args:
            criterion: Name of the criterion (e.g., "Age Requirement")
            rule_type: Type of rule (boolean, numeric, string, enum)
            requirement: Human-readable requirement description
            evaluator_str: Safe evaluator expression
        """
        self.criterion = criterion
        self.rule_type = rule_type
        self.requirement = requirement
        self.evaluator_str = evaluator_str
        self.evaluator = self._parse_safe_evaluator(evaluator_str)
    
    def _parse_safe_evaluator(self, evaluator_str: str) -> Callable:
        """
        Parse evaluator string into a safe callable function.
        
        This method converts lambda expressions into safe evaluation functions
        without using eval(). It supports common patterns like:
        - lambda u: u.get('age', 0) >= 18
        - lambda u: u.get('income', 0) <= 300000
        - lambda u: u.get('ownsLand', False)
        
        Args:
            evaluator_str: Lambda expression as string
            
        Returns:
            Callable function that evaluates the rule
        """
        # Remove 'lambda u:' prefix and whitespace
        expr = evaluator_str.strip()
        if expr.startswith('lambda u:'):
            expr = expr[9:].strip()
        elif expr.startswith('lambda'):
            # Handle other lambda formats
            expr = expr.split(':', 1)[1].strip()
        
        # Parse the expression and create a safe evaluator
        return self._create_safe_evaluator(expr)
    
    def _create_safe_evaluator(self, expr: str) -> Callable:
        """
        Create a safe evaluator function from an expression.
        
        Supports patterns like:
        - u.get('field', default) OPERATOR value
        - u.get("field", default) OPERATOR value
        - u.get('field', default)
        - u['field'] OPERATOR value
        - value1 <= u.get('field', default) <= value2 (chained comparison)
        
        Args:
            expr: Expression string
            
        Returns:
            Callable function
        """
        # Pattern: chained comparison (e.g., 18 <= u.get('age', 0) <= 60)
        pattern_chained = r"(\d+(?:\.\d+)?)\s*<=\s*u\.get\(['\"](\w+)['\"]\s*,\s*([^)]+)\)\s*<=\s*(\d+(?:\.\d+)?)"
        match = re.match(pattern_chained, expr)
        if match:
            min_val, field, default, max_val = match.groups()
            return self._create_range_evaluator(field, default, min_val, max_val)
        
        # Pattern: u.get('field', default) >= value (with single or double quotes)
        pattern1 = r"u\.get\(['\"](\w+)['\"]\s*,\s*([^)]+)\)\s*([><=!]+)\s*(.+)"
        match = re.match(pattern1, expr)
        if match:
            field, default, op, value = match.groups()
            return self._create_comparison_evaluator(field, default, op, value)
        
        # Pattern: u.get('field', default) (boolean check with single or double quotes)
        pattern2 = r"u\.get\(['\"](\w+)['\"]\s*,\s*([^)]+)\)"
        match = re.match(pattern2, expr)
        if match:
            field, default = match.groups()
            return self._create_boolean_evaluator(field, default)
        
        # Pattern: u['field'] >= value
        pattern3 = r"u\[['\"](\w+)['\"]\]\s*([><=!]+)\s*(.+)"
        match = re.match(pattern3, expr)
        if match:
            field, op, value = match.groups()
            return self._create_comparison_evaluator(field, 'None', op, value)
        
        # Fallback: return a function that always returns False
        logger.warning(f"Could not parse evaluator expression: {expr}")
        return lambda u: False
    
    def _create_comparison_evaluator(self, field: str, default: str, op: str, value: str) -> Callable:
        """Create a comparison evaluator function."""
        # Parse default value
        default_val = self._parse_value(default)
        
        # Parse comparison value
        comp_val = self._parse_value(value)
        
        # Get operator function
        op_func = {
            '>=': operator.ge,
            '<=': operator.le,
            '>': operator.gt,
            '<': operator.lt,
            '==': operator.eq,
            '!=': operator.ne,
        }.get(op, operator.eq)
        
        def evaluator(u: Dict) -> bool:
            user_val = u.get(field, default_val)
            try:
                return op_func(user_val, comp_val)
            except (TypeError, ValueError):
                return False
        
        return evaluator
    
    def _create_range_evaluator(self, field: str, default: str, min_val: str, max_val: str) -> Callable:
        """Create a range evaluator function for chained comparisons."""
        default_val = self._parse_value(default)
        min_value = self._parse_value(min_val)
        max_value = self._parse_value(max_val)
        
        def evaluator(u: Dict) -> bool:
            user_val = u.get(field, default_val)
            try:
                return min_value <= user_val <= max_value
            except (TypeError, ValueError):
                return False
        
        return evaluator
    
    def _create_boolean_evaluator(self, field: str, default: str) -> Callable:
        """Create a boolean evaluator function."""
        default_val = self._parse_value(default)
        
        def evaluator(u: Dict) -> bool:
            return bool(u.get(field, default_val))
        
        return evaluator
    
    def _parse_value(self, value_str: str) -> Any:
        """Parse a value string into appropriate Python type."""
        value_str = value_str.strip()
        
        # Boolean
        if value_str == 'True':
            return True
        if value_str == 'False':
            return False
        
        # None
        if value_str == 'None':
            return None
        
        # Number
        try:
            if '.' in value_str:
                return float(value_str)
            return int(value_str)
        except ValueError:
            pass
        
        # String (remove quotes)
        if value_str.startswith(("'", '"')) and value_str.endswith(("'", '"')):
            return value_str[1:-1]
        
        return value_str
    
    def evaluate(self, user_info: Dict) -> Tuple[bool, str]:
        """
        Evaluate the rule against user information.
        
        Args:
            user_info: Dictionary containing user information
            
        Returns:
            Tuple of (met: bool, user_value: str)
        """
        try:
            result = self.evaluator(user_info)
            
            # Format user value based on rule type
            if self.rule_type == 'boolean':
                user_value = 'Yes' if result else 'No'
                met = bool(result)
            elif self.rule_type == 'numeric':
                # Extract the actual numeric value from user_info
                # Try common numeric fields
                for field in ['age', 'income', 'landSize']:
                    if field in self.evaluator_str:
                        user_value = str(user_info.get(field, 'N/A'))
                        break
                else:
                    user_value = 'N/A'
                met = bool(result)
            elif self.rule_type == 'string':
                # Extract string value
                for field in ['state', 'category', 'occupation', 'gender']:
                    if field in self.evaluator_str:
                        user_value = str(user_info.get(field, 'N/A'))
                        break
                else:
                    user_value = str(result)
                met = bool(result)
            else:
                user_value = str(result)
                met = bool(result)
            
            return met, user_value
            
        except Exception as e:
            logger.error(f"Failed to evaluate rule '{self.criterion}': {e}")
            return False, 'Error evaluating criterion'


class SchemeRules:
    """
    Collection of eligibility rules for a scheme.
    
    This class manages all eligibility rules for a scheme and provides
    methods to evaluate them collectively.
    """
    
    def __init__(self, scheme_id: str):
        """
        Initialize scheme rules.
        
        Args:
            scheme_id: Unique identifier for the scheme
        """
        self.scheme_id = scheme_id
        self.rules: List[EligibilityRule] = []
    
    def add_rule(self, rule: EligibilityRule) -> None:
        """
        Add an eligibility rule to the collection.
        
        Args:
            rule: EligibilityRule instance to add
        """
        self.rules.append(rule)
    
    def add_rule_from_dict(self, rule_dict: Dict) -> None:
        """
        Add an eligibility rule from a dictionary.
        
        Args:
            rule_dict: Dictionary containing rule data
        """
        rule = EligibilityRule(
            criterion=rule_dict.get('criterion', ''),
            rule_type=rule_dict.get('type', 'boolean'),
            requirement=rule_dict.get('requirement', ''),
            evaluator_str=rule_dict.get('evaluator', '')
        )
        self.add_rule(rule)
    
    def evaluate_all(self, user_info: Dict) -> Dict[str, Any]:
        """
        Evaluate all rules against user information.
        
        Args:
            user_info: Dictionary containing user information
            
        Returns:
            Dictionary with evaluation results:
            {
                'eligible': bool,
                'criteria': List[Dict],
                'met_count': int,
                'total_count': int
            }
        """
        results = []
        
        for rule in self.rules:
            met, user_value = rule.evaluate(user_info)
            
            results.append({
                'criterion': rule.criterion,
                'required': rule.requirement,
                'userValue': user_value,
                'met': met
            })
        
        met_count = sum(1 for r in results if r['met'])
        total_count = len(results)
        eligible = met_count == total_count
        
        return {
            'eligible': eligible,
            'criteria': results,
            'met_count': met_count,
            'total_count': total_count
        }


@router.post("/eligibility", status_code=status.HTTP_200_OK)
async def check_eligibility(
    request: Request,
    eligibility_request: EligibilityRequest
):
    """
    Check scheme eligibility using rule-based logic.
    
    This endpoint implements a transparent, rule-based eligibility engine
    that evaluates user information against scheme criteria without using
    AI inference. All decisions are deterministic and explainable.
    
    Args:
        request: FastAPI Request object
        eligibility_request: Validated EligibilityRequest from request body
    
    Returns:
        EligibilityResponse with eligibility result including:
        - eligible: Boolean indicating eligibility status
        - explanation: Detailed breakdown of each criterion
        - schemeDetails: Information about the scheme and application process
        - alternativeSchemes: Suggestions if not eligible
    """
    # Get correlation ID from request state (set by middleware)
    correlation_id = getattr(request.state, 'correlation_id', None)
    
    logger.info("Processing eligibility check request", extra={'correlation_id': correlation_id})
    
    # Validate scheme ID
    try:
        scheme_id = validate_scheme_id(eligibility_request.schemeId)
    except ValueError as e:
        error_body = {
            'error': 'ValidationError',
            'message': str(e),
            'field': 'schemeId',
            'timestamp': get_current_timestamp()
        }
        return JSONResponse(
            status_code=status.HTTP_400_BAD_REQUEST,
            content=error_body
        )
    
    # Get user info and apply data minimization
    user_info_raw = eligibility_request.userInfo.dict()
    
    # Anonymize and filter user info to essential fields only
    user_info_anonymized = anonymize_user_info(user_info_raw)
    
    # Validate data minimization compliance
    if not validate_data_minimization(user_info_anonymized):
        logger.error("Data minimization validation failed", extra={'correlation_id': correlation_id})
        error_body = {
            'error': 'DataPrivacyViolation',
            'message': 'User information contains prohibited fields',
            'timestamp': get_current_timestamp()
        }
        return JSONResponse(
            status_code=status.HTTP_400_BAD_REQUEST,
            content=error_body
        )
    
    # Log data access for audit
    session_id = request.headers.get('X-Session-Id', 'unknown')
    log_data_access(
        operation='read',
        data_type='user_info',
        session_id=session_id,
        fields_accessed=list(user_info_anonymized.keys())
    )
    
    logger.info(f"Checking eligibility for scheme: {scheme_id}", extra={'correlation_id': correlation_id})
    
    # Get scheme from DynamoDB
    table = get_dynamodb_table()
    scheme = get_scheme(table, scheme_id)
    
    if not scheme:
        logger.warning(f"Scheme not found: {scheme_id}", extra={'correlation_id': correlation_id})
        error_body = {
            'error': 'SchemeNotFound',
            'message': f"Scheme with ID '{scheme_id}' does not exist",
            'timestamp': get_current_timestamp()
        }
        return JSONResponse(
            status_code=status.HTTP_404_NOT_FOUND,
            content=error_body
        )
    
    # Build scheme rules engine
    scheme_rules = SchemeRules(scheme_id)
    
    # Load eligibility rules
    eligibility_rules = scheme.get('eligibilityRules', [])
    if not eligibility_rules:
        logger.warning(f"No eligibility rules found for scheme: {scheme_id}", extra={'correlation_id': correlation_id})
        error_body = {
            'error': 'ConfigurationError',
            'message': f"Scheme '{scheme_id}' has no eligibility rules configured",
            'timestamp': get_current_timestamp()
        }
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content=error_body
        )
    
    for rule_dict in eligibility_rules:
        scheme_rules.add_rule_from_dict(rule_dict)
    
    logger.info(f"Loaded {len(scheme_rules.rules)} eligibility rules", extra={'correlation_id': correlation_id})
    
    # Evaluate all eligibility rules
    evaluation_result = scheme_rules.evaluate_all(user_info_anonymized)
    
    eligible = evaluation_result['eligible']
    criteria_results = evaluation_result['criteria']
    
    logger.info(
        f"Eligibility evaluation complete: eligible={eligible}, "
        f"met={evaluation_result['met_count']}/{evaluation_result['total_count']}",
        extra={'correlation_id': correlation_id}
    )
    
    # Generate comprehensive explanation
    explanation = generate_explanation(
        criteria_results,
        eligible,
        evaluation_result['met_count'],
        evaluation_result['total_count']
    )
    
    # Get scheme details
    scheme_details = SchemeDetails(
        name=scheme.get('name', ''),
        benefits=scheme.get('benefits', ''),
        applicationProcess=scheme.get('applicationSteps', []),
        requiredDocuments=scheme.get('documents', [])
    )
    
    # Get alternative schemes if not eligible
    alternative_schemes = None
    if not eligible:
        logger.info("User not eligible, fetching alternative schemes", extra={'correlation_id': correlation_id})
        alternative_schemes = get_alternative_schemes(
            table,
            scheme.get('category', ''),
            scheme_id
        )
        
        if alternative_schemes:
            logger.info(f"Found {len(alternative_schemes)} alternative schemes", extra={'correlation_id': correlation_id})
    
    # Create response
    response = EligibilityResponse(
        eligible=eligible,
        explanation=explanation,
        schemeDetails=scheme_details,
        alternativeSchemes=alternative_schemes
    )
    
    logger.info("Eligibility check completed successfully", extra={'correlation_id': correlation_id})
    return response.dict()


def get_scheme(table, scheme_id: str) -> Optional[Dict[str, Any]]:
    """
    Retrieve scheme from DynamoDB.
    
    Args:
        table: DynamoDB table resource
        scheme_id: Unique scheme identifier
        
    Returns:
        Scheme dictionary or None if not found
    """
    try:
        response = table.get_item(
            Key={
                'PK': f'SCHEME#{scheme_id}',
                'SK': 'METADATA'
            }
        )
        
        item = response.get('Item')
        
        if item:
            logger.info(f"Retrieved scheme: {scheme_id}")
        else:
            logger.warning(f"Scheme not found in database: {scheme_id}")
        
        return item
        
    except Exception as e:
        logger.error(f"Failed to retrieve scheme '{scheme_id}': {e}")
        return None


def generate_explanation(
    criteria_results: List[Dict],
    eligible: bool,
    met_count: int,
    total_count: int
) -> EligibilityExplanation:
    """
    Generate comprehensive human-readable explanation of eligibility decision.
    
    This function creates detailed explanations that help users understand
    exactly why they are or aren't eligible for a scheme, promoting
    transparency and trust.
    
    Args:
        criteria_results: List of criterion evaluation results
        eligible: Overall eligibility status
        met_count: Number of criteria met
        total_count: Total number of criteria
        
    Returns:
        EligibilityExplanation with detailed breakdown
    """
    criteria = [
        EligibilityCriterion(**result)
        for result in criteria_results
    ]
    
    if eligible:
        # Generate positive explanation
        summary = (
            f"You are eligible for this scheme. "
            f"You meet all {total_count} eligibility criteria."
        )
        
        if total_count > 0:
            summary += " You can proceed with the application process."
    else:
        # Generate detailed explanation of why not eligible
        unmet_count = total_count - met_count
        unmet_criteria = [c.criterion for c in criteria if not c.met]
        
        if unmet_count == 1:
            summary = (
                f"You are not eligible for this scheme. "
                f"You do not meet 1 out of {total_count} criteria. "
            )
        else:
            summary = (
                f"You are not eligible for this scheme. "
                f"You do not meet {unmet_count} out of {total_count} criteria. "
            )
        
        # Add specific unmet criteria
        if unmet_criteria:
            if len(unmet_criteria) == 1:
                summary += f"Specifically: {unmet_criteria[0]}."
            elif len(unmet_criteria) == 2:
                summary += f"Specifically: {unmet_criteria[0]} and {unmet_criteria[1]}."
            else:
                criteria_list = ', '.join(unmet_criteria[:-1])
                summary += f"Specifically: {criteria_list}, and {unmet_criteria[-1]}."
        
        # Add helpful message
        summary += " Please check the alternative schemes that may be suitable for you."
    
    return EligibilityExplanation(
        criteria=criteria,
        summary=summary
    )


def get_alternative_schemes(
    table,
    category: str,
    exclude_scheme_id: str,
    limit: int = 3
) -> Optional[List[Dict[str, str]]]:
    """
    Get alternative schemes in the same category.
    
    When a user is not eligible for a scheme, this function suggests
    alternative schemes in the same category that they might qualify for.
    
    Args:
        table: DynamoDB table resource
        category: Scheme category to search in
        exclude_scheme_id: Scheme ID to exclude from results
        limit: Maximum number of alternatives to return
        
    Returns:
        List of alternative scheme dictionaries or None if none found
    """
    if not category:
        logger.warning("No category provided for alternative schemes")
        return None
    
    try:
        response = table.query(
            IndexName='CategoryIndex',
            KeyConditionExpression='category = :category',
            ExpressionAttributeValues={
                ':category': category
            },
            Limit=limit + 5  # Get extra to account for filtering
        )
        
        schemes = response.get('Items', [])
        
        if not schemes:
            logger.info(f"No schemes found in category: {category}")
            return None
        
        # Filter out the current scheme and format results
        alternatives = []
        for scheme in schemes:
            scheme_id = scheme.get('schemeId', '')
            
            # Skip the current scheme
            if scheme_id == exclude_scheme_id:
                continue
            
            # Skip if missing required fields
            if not scheme.get('name'):
                continue
            
            alternatives.append({
                'id': scheme_id,
                'name': scheme.get('name', ''),
                'reason': f"Alternative {category} scheme that may suit your needs"
            })
            
            # Stop when we have enough alternatives
            if len(alternatives) >= limit:
                break
        
        return alternatives if alternatives else None
        
    except Exception as e:
        logger.error(f"Failed to get alternative schemes in category '{category}': {e}")
        return None
