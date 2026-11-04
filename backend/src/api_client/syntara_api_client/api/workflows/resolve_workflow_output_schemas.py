from http import HTTPStatus
from typing import Any

import httpx

from ... import errors
from ...client import AuthenticatedClient, Client
from ...models.detailed_validation_problem_detail import DetailedValidationProblemDetail
from ...models.error_data import ErrorData
from ...models.workflow_output_schemas_request import WorkflowOutputSchemasRequest
from ...models.workflow_output_schemas_response import WorkflowOutputSchemasResponse
from ...types import Response


def _get_kwargs(
    *,
    body: WorkflowOutputSchemasRequest,
) -> dict[str, Any]:
    headers: dict[str, Any] = {}

    _kwargs: dict[str, Any] = {
        "method": "post",
        "url": "/workflows/output-schemas",
    }

    _kwargs["json"] = body.to_dict()

    headers["Content-Type"] = "application/json"

    _kwargs["headers"] = headers
    return _kwargs


def _parse_response(
    *, client: AuthenticatedClient | Client, response: httpx.Response
) -> DetailedValidationProblemDetail | ErrorData | WorkflowOutputSchemasResponse | None:
    if response.status_code == 200:
        response_200 = WorkflowOutputSchemasResponse.from_dict(response.json())

        return response_200

    if response.status_code == 400:
        response_400 = ErrorData.from_dict(response.json())

        return response_400

    if response.status_code == 401:
        response_401 = ErrorData.from_dict(response.json())

        return response_401

    if response.status_code == 422:
        response_422 = DetailedValidationProblemDetail.from_dict(response.json())

        return response_422

    if response.status_code == 429:
        response_429 = ErrorData.from_dict(response.json())

        return response_429

    if response.status_code == 500:
        response_500 = ErrorData.from_dict(response.json())

        return response_500

    if client.raise_on_unexpected_status:
        raise errors.UnexpectedStatus(response.status_code, response.content)
    else:
        return None


def _build_response(
    *, client: AuthenticatedClient | Client, response: httpx.Response
) -> Response[DetailedValidationProblemDetail | ErrorData | WorkflowOutputSchemasResponse]:
    return Response(
        status_code=HTTPStatus(response.status_code),
        content=response.content,
        headers=response.headers,
        parsed=_parse_response(client=client, response=response),
        request=response.request,
        is_success=response.is_success,
    )


def sync_detailed(
    *,
    client: AuthenticatedClient,
    body: WorkflowOutputSchemasRequest,
) -> Response[DetailedValidationProblemDetail | ErrorData | WorkflowOutputSchemasResponse]:
    """Resolve workflow node output schemas

     Resolve expected output schemas for the supplied draft nodes without saving a workflow.

    Requires authentication but no workflow/project permission because this is a stateless,
    side-effect-free operation over caller-supplied node configuration. Form definitions are
    parsed locally; expressions, dynamic option queries, integrations, and workflow activities
    are never evaluated.

    Args:
        body (WorkflowOutputSchemasRequest):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        Response[DetailedValidationProblemDetail | ErrorData | WorkflowOutputSchemasResponse]
    """

    kwargs = _get_kwargs(
        body=body,
    )

    response = client.get_httpx_client().request(
        **kwargs,
    )

    return _build_response(client=client, response=response)


def sync(
    *,
    client: AuthenticatedClient,
    body: WorkflowOutputSchemasRequest,
) -> DetailedValidationProblemDetail | ErrorData | WorkflowOutputSchemasResponse | None:
    """Resolve workflow node output schemas

     Resolve expected output schemas for the supplied draft nodes without saving a workflow.

    Requires authentication but no workflow/project permission because this is a stateless,
    side-effect-free operation over caller-supplied node configuration. Form definitions are
    parsed locally; expressions, dynamic option queries, integrations, and workflow activities
    are never evaluated.

    Args:
        body (WorkflowOutputSchemasRequest):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        DetailedValidationProblemDetail | ErrorData | WorkflowOutputSchemasResponse
    """

    return sync_detailed(
        client=client,
        body=body,
    ).parsed


async def asyncio_detailed(
    *,
    client: AuthenticatedClient,
    body: WorkflowOutputSchemasRequest,
) -> Response[DetailedValidationProblemDetail | ErrorData | WorkflowOutputSchemasResponse]:
    """Resolve workflow node output schemas

     Resolve expected output schemas for the supplied draft nodes without saving a workflow.

    Requires authentication but no workflow/project permission because this is a stateless,
    side-effect-free operation over caller-supplied node configuration. Form definitions are
    parsed locally; expressions, dynamic option queries, integrations, and workflow activities
    are never evaluated.

    Args:
        body (WorkflowOutputSchemasRequest):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        Response[DetailedValidationProblemDetail | ErrorData | WorkflowOutputSchemasResponse]
    """

    kwargs = _get_kwargs(
        body=body,
    )

    response = await client.get_async_httpx_client().request(**kwargs)

    return _build_response(client=client, response=response)


async def asyncio(
    *,
    client: AuthenticatedClient,
    body: WorkflowOutputSchemasRequest,
) -> DetailedValidationProblemDetail | ErrorData | WorkflowOutputSchemasResponse | None:
    """Resolve workflow node output schemas

     Resolve expected output schemas for the supplied draft nodes without saving a workflow.

    Requires authentication but no workflow/project permission because this is a stateless,
    side-effect-free operation over caller-supplied node configuration. Form definitions are
    parsed locally; expressions, dynamic option queries, integrations, and workflow activities
    are never evaluated.

    Args:
        body (WorkflowOutputSchemasRequest):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        DetailedValidationProblemDetail | ErrorData | WorkflowOutputSchemasResponse
    """

    return (
        await asyncio_detailed(
            client=client,
            body=body,
        )
    ).parsed
