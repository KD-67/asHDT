import strawberry
from backend.graphql.resolvers.queries import Query
from backend.graphql.resolvers.mutations import Mutation
from backend.graphql.resolvers.subscriptions import Subscription

schema = strawberry.Schema(
    query=Query,
    mutation=Mutation,
    subscription=Subscription,
)
