import logging
import sys

from neo4j import GraphDatabase
from neo4j.exceptions import ServiceUnavailable

# TODO:
#  [ ] Identical relation a->a checking?
#  [ ] Refresh whole graph for uniqueness & no identical relations
#  [ ] Raise error to Script instance to enhance error printing

# Underlying atomic query options for the helper. App is a bad name and I actually copied it from some tutorial.
class App:

    def __init__(self, url, user, password):
        self.driver = GraphDatabase.driver(url, auth=(user, password))

    def close(self):
        # Don't forget to close the driver connection when you are finished with it
        self.driver.close()

    def clear_all(self):
        with self.driver.session() as session:
            result = session.write_transaction(
                self._clear_all_return)
            return result

    @staticmethod
    def _clear_all_return(tx):
        result = tx.run("MATCH (n) DETACH DELETE n")
        return result

    def create_pm_prop(self, pnum, vol, part, sect, pg, tp):
        if self.check_prop_exists(pnum):
            logging.getLogger("PMNeo4jHelper").debug("Proposition {pnum} {tp}(updated)".format(pnum=pnum, tp=tp))
            with self.driver.session() as session:
                result = session.write_transaction(
                    self._update_pm_prop_and_return, pnum, vol, part, sect, pg, tp)
        else:
            logging.getLogger("PMNeo4jHelper").debug("Proposition {pnum} {tp}".format(pnum=pnum, tp=tp))
            with self.driver.session() as session:
                result = session.write_transaction(
                    self._create_pm_prop_and_return, pnum, vol, part, sect, pg, tp)

    @staticmethod
    def _create_pm_prop_and_return(tx, pnum, vol, part, sect, pg, tp):
        ch, thm = pnum.split(".")
        node = "n" + ch + "_" + thm
        result = tx.run(
            "CREATE(" + node + ":Prop" +
            "{volume:'" + vol + "'," +
            "part:'" + part + "'," +
            "section:'" + sect + "'," +
            "chapter:'" + ch + "'," +
            "number:'" + pnum + "'," +
            "page:'" + pg + "'," +
            "type:'" + tp + "'})")
        return result

    @staticmethod
    def _update_pm_prop_and_return(tx, pnum, vol, part, sect, pg, tp):
        ch, thm = pnum.split(".")
        result = tx.run(
            "MATCH (p:Prop {number: '" + pnum + "'}) " +
            "SET p.volume='" + vol + "'," +
            "p.part='" + part + "'," +
            "p.section='" + sect + "'," +
            "p.chapter='" + ch + "'," +
            "p.number='" + pnum + "'," +
            "p.page='" + pg + "'," +
            "p.type='" + tp + "'")
        return result

    def connect_pm(self, p1, p2):
        if not self.check_prop_exists(p1):
            logging.getLogger("PMNeo4jHelper").error("Proof relation error: {p1} not found for {p1}->{p2}".format(p1=p1, p2=p2))
        elif not self.check_prop_exists(p2):
            logging.getLogger("PMNeo4jHelper").error("Proof relation error: {p2} not found for {p1}->{p2}".format(p1=p1, p2=p2))
        elif not self.check_conn_exists(p1, p2):
            logging.getLogger("PMNeo4jHelper").debug(p2 + " <-[Proves]- " + p1)
            with self.driver.session() as session:
                result = session.write_transaction(self._connect_pm_prop, p1, p2)
                return result
        else:
            logging.getLogger("PMNeo4jHelper").debug("{p2} <-[Proves]- {p1}(already exists)".format(p1=p1, p2=p2))
            pass
        return None

    @staticmethod
    def _connect_pm_prop(tx, p1, p2):
        result = tx.run(
            "MATCH (a:Prop {number: '" + p1 + "'}) " +
            "MATCH (b:Prop {number: '" + p2 + "'})" +
            "CREATE (a)-[r:Proves]->(b)")
        return result

    def update_prop_name(self, p, name):
        # BUG: Cannot delete a prop's name if already assigned.
        if self.check_prop_exists(p):
            with self.driver.session() as session:
                result = session.write_transaction(self._update_prop_name_return, p, name)
                return result
        else:
            logging.getLogger("PMNeo4jHelper").error("No proposition {p} found in database for name {name}".format(p=p, name=name))
            pass

    @staticmethod
    def _update_prop_name_return(tx, p, name):
        result = tx.run(
            "MATCH (a:Prop {number: '" + p + "'})" +
            "SET a.name = '" + name + "'"
        )
        return result

    def check_prop_exists(self, p):
        with self.driver.session() as session:
            result = session.read_transaction(self._check_prop_exists_return, p)
            return False if result == 0 else True

    @staticmethod
    def _check_prop_exists_return(tx, p):
        query = "MATCH (n:Prop {number: '" + p + "'}) " + "RETURN count(n) AS count"
        try:
            result = tx.run(query).single()
            count = result["count"]
        except ServiceUnavailable as exception:
            logging.getLogger("PMNeo4jHelper").error("{query} raised an error: \n {exception}".format(
                query=query, exception=exception))
            raise
        return count

    def check_conn_exists(self, p1, p2):
        with self.driver.session() as session:
            result = session.read_transaction(self._check_conn_exists_return, p1, p2)
            return False if result == 0 else True

    @staticmethod
    def _check_conn_exists_return(tx, p1, p2):
        query = "MATCH " \
                "(p1:Prop {number: '" + p1 + "'})" \
                "-[r:Proves]->" \
                "(p2:Prop {number: '" + p2 + "'}) " \
                "RETURN count(r) AS count"
        try:
            result = tx.run(query).single()
            count = result["count"]
        except ServiceUnavailable as exception:
            logging.getLogger("PMNeo4jHelper").error("{query} raised an error: \n {exception}".format(
                query=query, exception=exception))
            raise
        return count
