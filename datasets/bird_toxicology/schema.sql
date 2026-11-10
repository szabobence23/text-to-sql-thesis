-- BIRD Mini-Dev (bird-bench.github.io, CC BY-SA 4.0), PostgreSQL version (minidev.zip, MINIDEV_postgresql/BIRD_dev.sql), database toxicology.
-- Written by database/import_bird.py.

CREATE TABLE public.atom (
    atom_id text NOT NULL,
    molecule_id text,
    element text
);

CREATE TABLE public.bond (
    bond_id text NOT NULL,
    molecule_id text,
    bond_type text
);

CREATE TABLE public.connected (
    atom_id text NOT NULL,
    atom_id2 text NOT NULL,
    bond_id text
);

CREATE TABLE public.molecule (
    molecule_id text NOT NULL,
    label text
);

ALTER TABLE ONLY public.atom
    ADD CONSTRAINT idx_16953_sqlite_autoindex_atom_1 PRIMARY KEY (atom_id);
ALTER TABLE ONLY public.bond
    ADD CONSTRAINT idx_16958_sqlite_autoindex_bond_1 PRIMARY KEY (bond_id);
ALTER TABLE ONLY public.connected
    ADD CONSTRAINT idx_16963_sqlite_autoindex_connected_1 PRIMARY KEY (atom_id, atom_id2);
ALTER TABLE ONLY public.molecule
    ADD CONSTRAINT idx_16968_sqlite_autoindex_molecule_1 PRIMARY KEY (molecule_id);
ALTER TABLE ONLY public.atom
    ADD CONSTRAINT atom_molecule_id_fkey FOREIGN KEY (molecule_id) REFERENCES public.molecule(molecule_id);
ALTER TABLE ONLY public.bond
    ADD CONSTRAINT bond_molecule_id_fkey FOREIGN KEY (molecule_id) REFERENCES public.molecule(molecule_id);
ALTER TABLE ONLY public.connected
    ADD CONSTRAINT connected_atom_id2_fkey FOREIGN KEY (atom_id2) REFERENCES public.atom(atom_id) ON UPDATE CASCADE ON DELETE CASCADE;
ALTER TABLE ONLY public.connected
    ADD CONSTRAINT connected_atom_id_fkey FOREIGN KEY (atom_id) REFERENCES public.atom(atom_id) ON UPDATE CASCADE ON DELETE CASCADE;
ALTER TABLE ONLY public.connected
    ADD CONSTRAINT connected_bond_id_fkey FOREIGN KEY (bond_id) REFERENCES public.bond(bond_id) ON UPDATE CASCADE ON DELETE CASCADE;
