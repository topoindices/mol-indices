import os
from rdkit import Chem
import networkx as nx
import logging
from rdkit import RDLogger
from rdkit.Chem.rdmolops import GetSymmSSSR
import pandas as pd

# Suppress RDKit warnings
RDLogger.DisableLog('rdApp.*')
logger = logging.getLogger(__name__)

def compute_indices(e, v_deg):
    ti = {k: 0.0 for k in [
        "m1","m2","sc","randic","a","g","h","hm","f","sdd","sombor",
        "abc","az","isi","bm","tm","gh","gbm","gtm","ga","hg",
        "hbm","htm","ha","bmg","bmh","bma","tmh","tma","tmg"
    ]}
    
    for a, k in e:
        x, y = v_deg[a], v_deg[k]
        
        # Calculate all indices
        ti["m1"] += x + y
        ti["m2"] += x * y
        ti["sc"] += 1 / (x + y)**0.5 if (x + y) > 0 else 0
        ti["randic"] += 1 / (x * y)**0.5 if (x * y) > 0 else 0
        ti["a"] += (x + y) / 2
        ti["g"] += (x * y)**0.5
        ti["h"] += 2 / (x + y) if (x + y) != 0 else 0
        ti["hm"] += (x + y)**2
        ti["f"] += x**2 + y**2
        ti["sdd"] += (x**2 + y**2) / (x * y) if (x * y) != 0 else 0
        ti["sombor"] += (x**2 + y**2)**0.5
        ti["abc"] += ((x + y - 2) / (x * y))**0.5 if (x * y) != 0 else 0
        ti["az"] += ((x * y) / (x + y - 2))**3 if (x + y - 2) != 0 else 0
        ti["isi"] += (x * y) / (x + y) if (x + y) != 0 else 0
        ti["bm"] += x + y + (x * y)
        ti["tm"] += x**2 + y**2 + (x * y)
        ti["gh"] += ((x * y)**0.5 * (x + y)) / 2
        ti["gbm"] += (x * y)**0.5 / ((x + y) + (x * y)) if ((x + y) + (x * y)) != 0 else 0
        ti["gtm"] += (x * y)**0.5 / (x**2 + y**2 + (x * y)) if (x**2 + y**2 + x * y) != 0 else 0
        ti["ga"] += (2 * (x * y)**0.5) / (x + y) if (x + y) != 0 else 0
        ti["hg"] += 2 / ((x * y)**0.5 * (x + y)) if (x * y != 0 and x + y != 0) else 0
        ti["hbm"] += 2 / ((x + y + (x * y)) * (x + y)) if (x + y != 0 and x + y + x*y != 0) else 0
        ti["htm"] += 2 / ((x**2 + y**2 + (x * y)) * (x + y)) if (x + y != 0 and x**2 + y**2 + x*y != 0) else 0
        ti["ha"] += 4 / (x * y) if x * y != 0 else 0
        ti["bmg"] += (x + y + (x * y)) / (x * y)**0.5 if x * y != 0 else 0
        ti["bmh"] += ((x + y + (x * y)) * (x + y)) / 2
        ti["bma"] += (2 * (x + y + (x * y))) / (x + y) if (x + y) != 0 else 0
        ti["tmh"] += ((x**2 + y**2 + (x * y)) * (x + y)) / 2
        ti["tma"] += (2 * (x**2 + y**2 + (x * y))) / (x + y) if (x + y) != 0 else 0
        ti["tmg"] += (x**2 + y**2 + x * y) / (x * y)**0.5 if x * y != 0 else 0
    
    # Round to 6 decimal places for cleaner output
    return {k: round(v, 6) for k, v in ti.items()}

def process_molecule_file(mol_file_path, mode, k=1):
    try:
        if not os.path.exists(mol_file_path) or os.path.getsize(mol_file_path) == 0:
            return None

        mol = Chem.MolFromMolFile(mol_file_path, removeHs=True)
        if not mol:
            return None

        G = nx.Graph()
        for atom in mol.GetAtoms():
            G.add_node(atom.GetIdx())
        for bond in mol.GetBonds():
            G.add_edge(bond.GetBeginAtomIdx(), bond.GetEndAtomIdx())

        if not G.edges():
            return None

        # Choose degree vs degree sum vs reverse_degree vs scaled_face modes
        if mode == 'degree':
            v_deg = dict(G.degree())
        elif mode == 'degreesum':
            v_deg = {node: sum(G.degree(n) for n in G.neighbors(node)) for node in G.nodes()}
        elif mode == 'reverse_degree':
            original_degrees = {atom.GetIdx(): atom.GetDegree() for atom in mol.GetAtoms()}
            max_deg = max(original_degrees.values(), default=0)
            
            v_deg = {
                idx: (max_deg - deg + k if k <= deg 
                      else max_deg if (max_deg - deg + k) % max_deg == 0 
                      else (max_deg - deg + k) % max_deg)
                for idx, deg in original_degrees.items()
            }
        elif mode in ['scaled_face_degree', 'scaled_face_degree_sum']:
            # Compute vertex degrees based on mode
            if mode == 'scaled_face_degree':
                v_deg = dict(G.degree())
            else:
                v_deg = {node: sum(G.degree(n) for n in G.neighbors(node)) for node in G.nodes()}
            
            # Process rings and edges
            r = list(Chem.GetSymmSSSR(mol))
            edge_count = {}
            for ring in r:
                for i in range(len(ring)):
                    a = ring[i]
                    b = ring[(i+1) % len(ring)]
                    edge = tuple(sorted((a, b)))
                    edge_count[edge] = edge_count.get(edge, 0) + 1
            
            b_e = [edge for edge, count in edge_count.items() if count == 1]
            results = {}
            
            if len(r) == 0:
                mol_e = list(G.edges())
                index_ti = compute_indices(mol_e, v_deg)
                results = index_ti
            else:
                has_degree_one = any(deg == 1 for deg in v_deg.values())
                p_v_deg = {atom.GetIdx(): atom.GetDegree() for atom in mol.GetAtoms()}
                if has_degree_one:
                    for bond in mol.GetBonds():
                        start_idx = bond.GetBeginAtomIdx()
                        end_idx = bond.GetEndAtomIdx()
                        if p_v_deg[start_idx] == 1 or p_v_deg[end_idx] == 1:
                            edge = tuple(sorted((start_idx, end_idx)))
                            b_e.append(edge)
                            b_e.append(edge)
                
                # Compute edge and ring indices
                e_f = compute_indices(b_e, v_deg) if b_e else {k: 0.0 for k in [
                    "m1","m2","sc","randic","a","g","h","hm","f","sdd","sombor",
                    "abc","az","isi","bm","tm","gh","gbm","gtm","ga","hg",
                    "hbm","htm","ha","bmg","bmh","bma","tmh","tma","tmg"
                ]}
                i_f = {}
                for key in e_f:
                    total = 0.0
                    for ring in r:
                        ring_edges = [(ring[i], ring[(i+1) % len(ring)]) for i in range(len(ring))]
                        ring_ti = compute_indices(ring_edges, v_deg)
                        total += ring_ti[key] / len(ring)
                    i_f[key] = total
                
                n_e, n_r, len_b_e = G.number_of_edges(), len(r), len(b_e)
                s_f = n_e / (n_r + 1) if (n_r + 1) != 0 else 0
                totals = {}
                for key in e_f:
                    if len_b_e != 0:
                        term = (e_f[key] / len_b_e) + i_f[key]
                    else:
                        term = i_f[key]
                    totals[key] = round(s_f * term, 6) if s_f != 0 else 0
                results = totals
            
            results["Filename"] = os.path.basename(mol_file_path)
            return results
        else:
            raise ValueError(f"Unknown mode: {mode}")

        edges = list(G.edges())
        index_ti = compute_indices(edges, v_deg)
        index_ti["Filename"] = os.path.basename(mol_file_path)
        return index_ti

    except Exception as e:
        logger.error(f"Error processing {mol_file_path}: {str(e)}")
        return None

def process_uploaded_files(uploaded_files, mode, k=1):  # Add k parameter
    results = []
    for path in uploaded_files:
        res = process_molecule_file(path, mode, k)  # Pass k here
        if res:
            results.append(res)
    logger.info(f"Processed {len(results)}/{len(uploaded_files)} files")
    return results