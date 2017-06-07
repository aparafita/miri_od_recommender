import pandas as pd
np = pd.np

from utils import path, run_query

RATINGS_QUERY = """
PREFIX rdf: <http://www.w3.org/1999/02/22-rdf-syntax-ns#>
PREFIX ont: <http://schema.org/ontology/>

SELECT ?user ?restaurant ?rating WHERE { 
    ?review rdf:type ont:Review .
    ?review ont:writtenBy ?user .
    ?review ont:about ?restaurant .
    ?review ont:rating ?rating 
}
"""


class Recommender:

    def __init__(
        self, ratings_filename=None, 
        user_min_ratings=10, restaurant_min_ratings=10,
        K=10
    ):
        """
            Given the ratings filename, 
            the min number of ratings for a user or restaurant to be considered,
            and the number of neighbors used for the prediction, 
            defines an instance used to predict ratings.

            If no filename is given, a query is perfomed to obtain the results.
        """

        self.K = K

        if ratings_filename is None:
            ratings = run_query(RATINGS_QUERY, use_prefixes=False)
        else:
            ratings = pd.read_csv(ratings_filename)

        # Before filtering, let's compute the mean ratings for all restaurants
        # This will be our "prior knowledge" that we will use when we don't know
        # the score to give to a restaurant.
        # We won't use the mean ratings directly, but the mean "likeability"
        # of a restaurant when we have standardized every user rating
        Xprior = ratings.copy()
        agg = Xprior.groupby('user').rating.agg(['mean', 'std']).reset_index()

        Xprior = Xprior.merge(agg)
        Xprior['rating'] = (Xprior['rating'] - Xprior['mean']) / Xprior['std']

        self.prior_ratings = Xprior.groupby('restaurant').rating.mean()
        self.restaurants = list(self.prior_ratings.index)


        # Filter the dataset
        restaurant_counts = ratings.groupby('restaurant').size()
        ratings = ratings[
            ratings.restaurant.isin(
                set(
                    restaurant_counts[
                        restaurant_counts >= restaurant_min_ratings
                    ].index
                )
            )
        ].copy()

        user_counts = ratings.groupby('user').size()
        ratings = ratings[
            ratings.user.isin(
                set(user_counts[user_counts >= user_min_ratings].index)
            )
        ].copy()

        ratings = ratings.pivot_table(
            index='user', columns='restaurant', values='rating', aggfunc='mean'
        )

        self.nusers, self.nitems = ratings.shape

        X = ratings.values.copy()

        means = np.nanmean(X, axis=1)
        X -= means.reshape((self.nusers, 1))

        stds = np.nanstd(X, axis=1)
        X /= stds.reshape((self.nusers, 1))

        voted = ~np.isnan(X)

        # Assign results to the instance
        self.ratings = ratings
        self.X = X
        self.voted = voted
        self.means = means
        self.stds = stds

        self._users = list(ratings.index)
        self._items = list(ratings.columns)


    def _intersection(self, user_voted):
        return [
            np.arange(self.nitems)[
                (user_voted * self.voted[n2,]) > 0
            ]
            
            for n2 in range(self.nusers)
        ]


    def _similarities(self, user_votes):
        user_voted = ~np.isnan(user_votes)

        res = []
        
        for n2, i in zip(range(self.nusers), self._intersection(user_voted)):
            u1, u2 = user_votes[i], self.X[n2, i]
            
            res.append(
                u1.dot(u2) / np.sqrt(u1.dot(u1) * u1.dot(u2))
            )
            
        return np.array(res)


    def _compute_predictions(self, user_votes, user_mean, user_std, K):
        """
            Predicts the ratings (user-based) for all possible items
            given the votes of any user.

            Parameters: 
                - user_votes: np.array with the user votes, already standardized
                - user_mean: mean score of the user votes
                - user_std: std of the user votes
                - K: number of neighbors to consider for the prediction
        """

        sims = np.nan_to_num(self._similarities(user_votes))
        predictions = []
        
        for item in range(self.nitems):
            if not np.isnan(user_votes[item]):
                predictions.append(user_votes[item])
                continue
            
            votes = self.voted[:, item]
            
            ratings = self.X[votes, item]
            users = np.arange(self.nusers)[votes]
            sims_f = sims[votes]
            
            neighs = (sims_f ** 2).argsort()[-K:] # take both >0 and <0
            pred = (
                sims_f[neighs].dot(ratings[neighs]) / 
                np.abs(sims_f[neighs]).sum()
            )
            
            predictions.append(pred)
            
        pred = pd.Series(predictions, index=self._items)
        # Add all items that could not be predicted due to cold-start
        pred = pred.reindex(self.restaurants) # this adds nans

        # For those items where we haven't got a rating, 
        # we'll use the prior rating 
        # (the mean rating accross the entire dataset)
        # These ratings, however, will be penalized with -1 std
        pred[np.isnan(pred)] = self.prior_ratings[np.isnan(pred)] - 1

        # Finally, compute the real ratings (readjusting the normalization)
        pred = (pred * user_std + user_mean)#.round().astype(int)
        
        pred = np.where(pred < 1, 1, pred)
        pred = np.where(pred > 5, 5, pred)
        
        return pd.Series(pred, index=self.restaurants)


    def predict(self, user):
        if type(user) in (list, tuple):
            user = np.array(user)
        elif type(user) == dict:
            user = np.array(
                [
                    user.get(item, np.nan)

                    for item in self._items
                ]
            )

        if type(user) == int:
            if user < 0 or user >= self.nusers:
                raise ValueError(
                    'When passing an integer, it must be the id of a user, '
                    'between 0 and %d - 1' % self.nusers
                )

            mean = self.means[user]
            std = self.stds[user]

            user = self.X[user, :]

        elif type(user) == np.ndarray:
            if len(user.shape) != 1 or len(user) != self.nitems:
                raise ValueError(
                    'user must be an np.array with %d ratings, '
                    'possible NaNs' % self.nitems
                )

            if not any(~np.isnan(user)):
                raise ValueError(
                    'This user doesn\'t have any ratings yet. '
                    'Rate some restaurants first.'
                )

            mean = np.nanmean(user)
            std = np.nanstd(user)

            if std == 0:
                raise ValueError(
                    'This user has a constant rating for all restaurants. '
                    'We can\'t recommend with that'
                )

            user = (user - mean) / std

        return self._compute_predictions(user, mean, std, self.K)


if __name__ == '__main__':
    rec = Recommender(path('data/ratings-matrix.csv.gz'))

    user = dict(
        zip(
            np.random.choice(rec.restaurants, 10, replace=False),
            np.random.randint(1, 5 + 1, 10)
        )
    )

    pred = rec.predict(user)
    print(pred)