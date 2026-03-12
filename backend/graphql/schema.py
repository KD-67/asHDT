import strawberry
from strawberry.tools import merge_types

from backend.graphql.subjects.queries      import SubjectQueries
from backend.graphql.subjects.mutations    import SubjectMutations
from backend.graphql.modules.queries       import ModuleQueries
from backend.graphql.modules.mutations     import ModuleMutations
from backend.graphql.datapoints.queries    import DatapointQueries
from backend.graphql.datapoints.mutations  import DatapointMutations
from backend.graphql.analysis.queries      import AnalysisQueries
from backend.graphql.analysis.mutations    import AnalysisMutations
from backend.graphql.analysis.subscriptions import AnalysisSubscriptions
from backend.graphql.markersets.queries    import MarkersetQueries
from backend.graphql.markersets.mutations  import MarkersetMutations

Query = merge_types(
    "Query",
    (SubjectQueries, ModuleQueries, DatapointQueries, AnalysisQueries, MarkersetQueries),
)

Mutation = merge_types(
    "Mutation",
    (SubjectMutations, ModuleMutations, DatapointMutations, AnalysisMutations, MarkersetMutations),
)

Subscription = merge_types(
    "Subscription",
    (AnalysisSubscriptions,),
)

schema = strawberry.Schema(
    query=Query,
    mutation=Mutation,
    subscription=Subscription,
)
