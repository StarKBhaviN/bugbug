# -*- coding: utf-8 -*-
# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this file,
# You can obtain one at http://mozilla.org/MPL/2.0/.

import logging

import xgboost
from imblearn.under_sampling import RandomUnderSampler
from sklearn.compose import ColumnTransformer
from sklearn.feature_extraction import DictVectorizer
from sklearn.pipeline import Pipeline

from bugbug import bug_features, bugzilla, feature_cleanup, utils
from bugbug.model import BugModel

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class RegressionRangeModel(BugModel):
    def __init__(self, lemmatization=False):
        BugModel.__init__(self, lemmatization)

        self.sampler = RandomUnderSampler(random_state=0)

        feature_extractors = [
            bug_features.HasSTR(),
            bug_features.Severity(),
            bug_features.Keywords({"regression", "regressionwindow-wanted"}),
            bug_features.IsCoverityIssue(),
            bug_features.HasCrashSignature(),
            bug_features.HasURL(),
            bug_features.HasW3CURL(),
            bug_features.HasGithubURL(),
            bug_features.Whiteboard(),
            bug_features.Patches(),
            bug_features.Landings(),
        ]

        cleanup_functions = [
            feature_cleanup.fileref(),
            feature_cleanup.url(),
            feature_cleanup.synonyms(),
        ]

        self.extraction_pipeline = Pipeline(
            [
                (
                    "bug_extractor",
                    bug_features.BugExtractor(feature_extractors, cleanup_functions),
                ),
                (
                    "union",
                    ColumnTransformer(
                        [
                            ("data", DictVectorizer(), "data"),
                            ("title", self.text_vectorizer(), "title"),
                            ("comments", self.text_vectorizer(), "comments"),
                        ]
                    ),
                ),
            ]
        )

        self.hyperparameter = {"n_jobs": utils.get_physical_cpu_count()}
        self.clf = xgboost.XGBClassifier(**self.hyperparameter)

    def get_labels(self):
        classes = {}

        for bug_data in bugzilla.get_bugs():
            if "regression" not in bug_data["keywords"]:
                continue

            bug_id = int(bug_data["id"])
            if "regressionwindow-wanted" in bug_data["keywords"]:
                classes[bug_id] = 0
            elif "cf_has_regression_range" in bug_data:
                if bug_data["cf_has_regression_range"] == "yes":
                    classes[bug_id] = 1
                elif bug_data["cf_has_regression_range"] == "no":
                    classes[bug_id] = 0
        logger.info(
            "%d bugs have regression range",
            sum(1 for label in classes.values() if label == 1),
        )
        logger.info(
            "%d bugs don't have a regression range",
            sum(1 for label in classes.values() if label == 0),
        )

        return classes, [0, 1]

    def get_feature_names(self):
        return self.extraction_pipeline.named_steps["union"].get_feature_names_out()
